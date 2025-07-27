from server import Server
from client import Client
import time
import random
import string


def random_4char_string():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=4))


def benchmark_oram(client, server, num_requests, key_space, ops=('read', 'write', 'delete')):
    latencies = []
    start_time = time.perf_counter()

    for _ in range(num_requests):
        op = random.choice(ops)
        a = random.randint(0, key_space - 1)
        data_ = random_4char_string() if op == 'write' else None

        req_start = time.perf_counter()
        client.Access(op, a, data_, server)
        req_end = time.perf_counter()

        latencies.append(req_end - req_start)

    end_time = time.perf_counter()

    # Metrics
    total_time = end_time - start_time
    avg_latency = sum(latencies) / len(latencies)
    throughput = num_requests / total_time

    print(f"Benchmark Results:")
    print(f"  Total requests:     {num_requests}")
    print(f"  Total time:         {total_time:.4f} seconds")
    print(f"  Avg latency:        {avg_latency * 1000:.4f} ms")
    print(f"  Throughput:         {throughput:.2f} requests/sec")

    return {
        'total_requests': num_requests,
        'total_time_sec': total_time,
        'avg_latency_ms': avg_latency * 1000,
        'throughput_rps': throughput
    }


# benchmark 1
def benchmark_throughput_vs_N(N_values, num_requests):
    results = []
    for N in N_values:
        print(f"\nTesting throughput for N = {N}")
        server = Server(N)
        client = Client(server)
        result = benchmark_oram(client, server, num_requests=num_requests, key_space=N)
        result['N'] = N
        results.append(result)
    return results


# Benchmark 2
def benchmark_latency_vs_target_throughput(target_throughputs, num_requests, N):
    results = []

    for target_rps in target_throughputs:
        print(f"\nTarget Throughput: {target_rps} req/sec")
        delay = 1.0 / target_rps  # delay between requests (in seconds)

        # Setup fresh ORAM instance
        server = Server(N)
        client = Client(server)

        latencies = []
        next_request_time = time.perf_counter()

        for _ in range(num_requests):
            # Random access operation
            op = random.choice(['read', 'write', 'delete'])
            a = random.randint(0, N - 1)
            data_ = random_4char_string() if op == 'write' else None

            # Measure latency of Access()
            start = time.perf_counter()
            client.Access(op, a, data_, server)
            end = time.perf_counter()
            latencies.append(end - start)

            # Wait to maintain target rate
            next_request_time += delay
            sleep_time = next_request_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Compute average latency
        avg_latency = sum(latencies) / len(latencies)
        avg_latency_ms = avg_latency * 1000
        print(f"Average Latency: {avg_latency_ms:.5f} ms")

        results.append({
            'target_throughput': target_rps,
            'avg_latency_ms': avg_latency_ms
        })

    return results


if __name__ == "__main__":
    # Benchmark 1: Throughput vs N (ORAM Size)
    Ns = [256, 1024, 4096, 16384]
    throughput_results = benchmark_throughput_vs_N(Ns, 10_000)

    # Benchmark 2: Latency vs Throughput
    throughputs_to_test = [500, 1000, 1500, 2000, 3000, 4000, 8000]
    results = benchmark_latency_vs_target_throughput(throughputs_to_test, 10000, 4096)

    for r in results:
        print(f"Throughput: {r['target_throughput']} req/s → Avg Latency: {r['avg_latency_ms']:.5f} ms")

