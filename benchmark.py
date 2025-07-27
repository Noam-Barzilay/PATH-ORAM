#!/usr/bin/env python

"""

bench_path_oram.py

==================

Micro-benchmark driver for the *non-recursive Path-ORAM* implementation.



What it measures

----------------

1. Throughput   (requests / second)            vs. DB size N   — single thread

2. Latency      (µs per request, median & p95) vs. throughput   — 1, 2, 4, 8 workers

3. Simple multicore scaling factor.



Results are printed as pretty tables and also dumped as JSON so you can plot

them with your favourite tool later.



Run

---

$ python bench_path_oram.py

"""

from __future__ import annotations



import json

import statistics as stats

import time

from collections import defaultdict

from functools import partial

from random import choice, random

from concurrent.futures import ThreadPoolExecutor, as_completed



from client import Client
from server import Server


# --------------------------------------------------------- workload helpers

def one_random_op(cli: Client, srv: Server, ids: list[int]):

    bid = choice(ids)

    r = random()

    if r < 0.34:

        cli.store_data(srv, bid, "DATA")

    elif r < 0.67:

        cli.retrieve_data(srv, bid)

    else:

        cli.delete_data(srv, bid, "DATA")





def run_sequential(N: int, ops: int) -> dict[str, float]:

    """Run *ops* sequential requests on DB of size *N*; return metrics."""

    srv = Server(N)

    cli = Client(srv)

    ids = list(range(N))



    t0 = time.perf_counter()

    for _ in range(ops):

        one_random_op(cli, srv, ids)

    total = time.perf_counter() - t0

    return {

        "N": N,

        "ops": ops,

        "throughput_rps": ops / total,

        "avg_latency_us": total / ops * 1e6,

    }





# ---------------------------------------------------------------- Parallel

def run_parallel(N: int, ops: int, workers: int) -> dict[str, float]:

    """

    Fire *ops* requests using *workers* independent ORAM clients.

    Latency samples are gathered per request.

    """

    ids = list(range(N))

    lat_samples: list[float] = []



    def worker_task(num_ops: int):

        srv = Server(N)

        cli = Client(srv)

        local_lat = []

        for _ in range(num_ops):

            t0 = time.perf_counter()

            bid = choice(ids)

            r = random()

            if r < 0.34:

                cli.store_data(srv, bid, "DATA")

            elif r < 0.67:

                cli.retrieve_data(srv, bid)

            else:

                cli.delete_data(srv, bid, "DATA")

            local_lat.append((time.perf_counter() - t0) * 1e6)  # µs

        return local_lat



    # split the total ops approximately evenly

    chunk = ops // workers

    leftover = ops - chunk * workers

    chunks = [chunk + 1 if i < leftover else chunk for i in range(workers)]



    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as ex:

        futures = [ex.submit(worker_task, n) for n in chunks]

        for f in futures:

            lat_samples.extend(f.result())

    total = time.perf_counter() - t0



    return {

        "workers": workers,

        "ops": ops,

        "throughput_rps": ops / total,

        "lat_med_us": stats.median(lat_samples),

        "lat_p95_us": stats.quantiles(lat_samples, n=20)[18],  # 95-th perc

    }





# ------------------------------------------------------------- benchmark A

def benchmark_throughput_vs_N(sizes=(256, 1024, 4096, 16384), ops_per_run=5000, runs=3):

    print("\n=== Throughput vs. N (single thread) ===")

    results = []

    for N in sizes:

        tputs, lats = [], []

        for _ in range(runs):

            m = run_sequential(N, ops_per_run)

            tputs.append(m["throughput_rps"])

            lats.append(m["avg_latency_us"])

        avg = {

            "N": N,

            "throughput_rps": stats.mean(tputs),

            "lat_us": stats.mean(lats),

        }

        results.append(avg)

        print(f" N={N:6} | {avg['throughput_rps']:9.0f} req/s | "

              f"{avg['lat_us']:6.1f} µs/req")

    return results





# ------------------------------------------------------------- benchmark B

def benchmark_latency_vs_workers(N=1024, ops=8000, runs=3, worker_set=(1, 2, 4, 8)):

    print(f"\n=== Latency vs. throughput (N={N}) ===")

    results = []

    for w in worker_set:

        tputs, medians, p95s = [], [], []

        for _ in range(runs):

            m = run_parallel(N, ops, w)

            tputs.append(m["throughput_rps"])

            medians.append(m["lat_med_us"])

            p95s.append(m["lat_p95_us"])

        avg = {

            "workers": w,

            "throughput_rps": stats.mean(tputs),

            "lat_med_us": stats.mean(medians),

            "lat_p95_us": stats.mean(p95s),

        }

        results.append(avg)

        scaling = avg["throughput_rps"] / results[0]["throughput_rps"]

        print(f" {w} worker(s) | {avg['throughput_rps']:9.0f} req/s | "

              f"{avg['lat_med_us']:6.1f} µs (median) | "

              f"{avg['lat_p95_us']:6.1f} µs (p95) | "

              f"×{scaling:4.2f} speed-up")

    return results





# ---------------------------------------------------------------------- main

if __name__ == "__main__":

    SEQ_RES = benchmark_throughput_vs_N()

    PAR_RES = benchmark_latency_vs_workers()



    with open("bench_oram.json", "w") as fp:

        json.dump({"throughput_vs_N": SEQ_RES, "lat_vs_workers": PAR_RES}, fp, indent=2)

    print("\n📈  Raw numbers written to bench_oram.json")