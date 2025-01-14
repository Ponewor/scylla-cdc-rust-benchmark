pub mod benchmark;

use atomic_counter::{AtomicCounter, ConsistentCounter, RelaxedCounter};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;

use clap::Parser;

use scylla::SessionBuilder;
use scylla_cdc::log_reader::CDCLogReaderBuilder;

use crate::benchmark::*;

#[derive(Parser)]
struct Args {
    /// Keyspace name
    #[clap(short, long)]
    keyspace: String,

    /// Table name
    #[clap(short, long)]
    table: String,

    /// Address of a node in source cluster
    #[clap(short, long)]
    hostname: String,

    /// Window size in seconds
    #[clap(long, default_value_t = 60.)]
    window_size: f64,

    /// Safety interval in seconds
    #[clap(long, default_value_t = 30.)]
    safety_interval: f64,

    /// Sleep interval in seconds
    #[clap(long, default_value_t = 2.)]
    sleep_interval: f64,

    /// Sleep interval in seconds
    #[clap(long, default_value_t = 10)]
    rows_count: usize,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let session = Arc::new(
        SessionBuilder::new()
            .known_node(args.hostname)
            .build()
            .await?,
    );
    let (sender, mut receiver) = mpsc::channel(1);
    let counter = Arc::new(ConsistentCounter::new(0));
    let limit = args.rows_count;
    let checksum = Arc::new(RelaxedCounter::new(0));
    let factory = Arc::new(BenchmarkConsumerFactory {
        counter,
        limit,
        sender: sender.clone(),
        checksum: Arc::clone(&checksum),
    });

    // To simulate Java behavior:
    // - start from the start of the first generation
    // - sleep for 1 ms (java does not sleep at all)
    let (mut reader, handle) = CDCLogReaderBuilder::new()
        .session(session)
        .keyspace(&args.keyspace)
        .table_name(&args.table)
        .window_size(Duration::from_secs_f64(args.window_size))
        .safety_interval(Duration::from_secs_f64(args.safety_interval))
        .sleep_interval(Duration::from_millis(1))
        .consumer_factory(factory)
        .start_timestamp(chrono::Duration::zero())
        .build()
        .await?;

    receiver.recv().await.unwrap();

    println!("Scylla-cdc-rust has read {} rows! The checksum is {}.", limit, checksum.get());
    reader.stop();
    handle.await
}
