import argparse
from cassandra.cluster import Cluster
import subprocess
import time

RATE_PER_SHARD = 5000

rust_binary = "rust-reader/target/release/scylla-cdc-rust-benchmark"
go_binary = "go-reader/go-reader"
java_binary = "java-reader/cdc-rust-benchmark/cdc-rust-benchmark"
scylla_bench_binary = "scylla-bench/scylla-bench"
keyspace = "scylla_bench"
table = "test"

time_command = "/usr/bin/time -v"


def prepare_database(source: str, partition_count: int, clustering_row_count: int, max_rate: int):
    cluster = Cluster([source])
    session = cluster.connect()
    session.execute(f"CREATE KEYSPACE IF NOT EXISTS {keyspace} "
                    f"WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 3}}")
    session.execute(f"CREATE TABLE IF NOT EXISTS {keyspace}.{table} "
                    f"(pk bigint, ck bigint, v blob, primary key (pk, ck))"
                    f"WITH cdc = {{'enabled': 'true'}} AND compression = {{ }}")

    print("Writing the test data to the cluster...")
    command = [scylla_bench_binary,
               "-nodes", source,
               "-mode", "write",
               "-workload", "sequential",
               "-partition-count", f"{partition_count}",
               "-clustering-row-count", f"{clustering_row_count}",
               "-max-rate", f"{max_rate}"]

    subprocess.run(command, stdout=subprocess.DEVNULL)

    print("Data written!")


def run_rust(source: str, rows_count: int, window_size: int):
    command = ["/usr/bin/time", "-v",
               rust_binary,
               "--keyspace", keyspace,
               "--table", table,
               "--hostname", f"{source}:9042",
               "--rows-count", f"{rows_count}",
               "--window-size", f"{window_size}.0"]

    print("Running the benchmark for scylla-cdc-rust.")
    with open(f"results/rust_{window_size}.txt", "w") as output_file:
        subprocess.run(command, stdout=output_file, stderr=output_file)

def run_go(source: str, rows_count: int, window_size: int):
    command = ["/usr/bin/time", "-v",
               go_binary,
               "--keyspace", keyspace,
               "--table", table,
               "--hostname", f"{source}:9042",
               "--rows-count", f"{rows_count}",
               "--window-size", f"{window_size}"]

    print("Running the benchmark for scylla-cdc-go.")
    with open(f"results/go_{window_size}.txt", "w") as output_file:
        subprocess.run(command, stdout=output_file, stderr=output_file)

def run_java(source: str, rows_count: int, window_size: int):
    command = ["/usr/bin/time", "-v",
               java_binary,
               "-k", keyspace,
               "-t", table,
               "-s", source,
               "-c", f"{rows_count}",
               "-w", f"{window_size * 1000}"]

    print("Running the benchmark for scylla-cdc-java.")
    with open(f"results/java_{window_size}.txt", "w") as output_file:
        subprocess.run(command, stdout=output_file, stderr=output_file)


def run_tests(source: str, rows_count: int, window_size: int):
    print(f"Running the benchmark with window size equal to {window_size} seconds.")
#     run_rust(source, rows_count, window_size)
    run_go(source, rows_count, window_size)
#     run_java(source, rows_count, window_size)
    print(f"The benchmark for window size {window_size} has finished!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str)
    parser.add_argument("--partition_count", default=40000, type=int)
    parser.add_argument("--clustering_row_count", default=2000, type=int)
    parser.add_argument("--shards", default=4, type=int)

    args = parser.parse_args()
    source = args.source

    prepare_database(source, args.partition_count, args.clustering_row_count, args.shards * RATE_PER_SHARD)

    # After creating the database, sleep for 60 seconds so that the window size doesn't ruin the benchmark.
    print("Waiting...")
    time.sleep(60.0)

    rows_count = args.partition_count * args.clustering_row_count

    print("Starting the benchmark.")

    run_tests(source, rows_count, 15)
    run_tests(source, rows_count, 30)
    run_tests(source, rows_count, 60)


main()
