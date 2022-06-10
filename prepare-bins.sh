#!/usr/bin/env bash
mkdir results

cd rust-reader
cargo build --release

cd ../go-reader
go build

cd ../java-reader/cdc-rust-benchmark
mvn package
chmod 744 cdc-rust-benchmark

cd ../../scylla-bench
go install . && go build .
