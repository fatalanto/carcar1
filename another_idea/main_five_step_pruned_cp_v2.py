import argparse
import csv
import logging
from collections import deque

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

MAZE_FILE = r"big_maze_114.csv"
START_NODE = 25
START_FACING = "S"
RUN_TIME_LIMIT = 65.0
RESERVE_SECONDS = 3.0
TAIL_SWITCH_SECONDS = 9.0

# Measured timing model
DEADEND_OUT_AND_BACK_SECONDS = 1.72
TURN_AND_GO_TO_NEXT_NODE_SECONDS = 1.17
GO_THROUGH_ONE_NODE_TO_SECOND_NODE_SECONDS = 1.53

FACINGS = ['N', 'E', 'S', 'W']
FIDX = {f: i for i, f in enumerate(FACINGS)}

def load_graph(filename):
    graph = {}
    with open(filename, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            node = int(row["index"])
            nb = {}
            if row.get("North"): nb["N"] = int(float(row["North"]))
            if row.get("East"):  nb["E"] = int(float(row["East"]))
            if row.get("South"): nb["S"] = int(float(row["South"]))
            if row.get("West"):  nb["W"] = int(float(row["West"]))
            graph[node] = nb
    return graph

def build_coordinates(graph, start=START_NODE):
    delta = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
    coord = {start: (0, 0)}
    q = deque([start])
    while q:
        u = q.popleft()
        x, y = coord[u]
        for d, v in graph[u].items():
            if v not in coord:
                dx, dy = delta[d]
                coord[v] = (x + dx, y + dy)
                q.append(v)
    return coord

def compute_scores(graph, start=START_NODE):
    coord = build_coordinates(graph, start)
    sx, sy = coord[start]
    # New rule: score is 3x the original version
    return {node: 30 * (abs(x - sx) + abs(y - sy)) for node, (x, y) in coord.items()}

def treasure_nodes(graph, start=START_NODE):
    return sorted([n for n, edges in graph.items() if len(edges) == 1 and n != start])

def bfs_path(graph, start, goal):
    q = deque([[start]])
    visited = {start}
    while q:
        path = q.popleft()
        u = path[-1]
        if u == goal:
            return path
        for v in graph[u].values():
            if v not in visited:
                visited.add(v)
                q.append(path + [v])
    return []

def direction_between(graph, u, v):
    for d, nxt in graph[u].items():
        if nxt == v:
            return d
    raise ValueError(f"No edge from {u} to {v}")

def move_time_for_path(graph, path, start_facing):
    """
    Timing model used in the discussion:
    - If the target is an adjacent dead-end treasure, going in, sensing UID, turning back,
      and returning to the original node takes 1.72s.
    - Otherwise, the first edge in a movement group costs 1.17s.
    - Continuing straight through one sensed node to the second node costs 1.53s.
    Returns:
      total_time, end_node, end_facing, touched(list of (treasure, touch_time_from_start_of_segment))
    """
    if len(path) < 2:
        return 0.0, path[0], start_facing, []

    current_node = path[0]
    current_facing = start_facing
    total = 0.0
    touched = []
    i = 1

    while i < len(path):
        nxt = path[i]

        if len(graph[nxt]) == 1 and i == len(path) - 1:
            total += DEADEND_OUT_AND_BACK_SECONDS
            touched.append((nxt, total))
            return total, current_node, current_facing, touched

        move_dir = direction_between(graph, current_node, nxt)
        total += TURN_AND_GO_TO_NEXT_NODE_SECONDS
        current_node = nxt
        current_facing = move_dir
        i += 1

        while i < len(path):
            nxt2 = path[i]
            d2 = direction_between(graph, current_node, nxt2)
            if d2 == current_facing and not (len(graph[nxt2]) == 1 and i == len(path) - 1):
                total += GO_THROUGH_ONE_NODE_TO_SECOND_NODE_SECONDS
                current_node = nxt2
                i += 1
            else:
                break

    return total, current_node, current_facing, touched

def upper_bound_remaining(scores, remaining):
    return sum(scores[t] for t in remaining)

def better_label(existing, score, time_used):
    for s2, t2 in existing:
        if s2 >= score and t2 <= time_used + 1e-12:
            return False
    keep = []
    for s2, t2 in existing:
        if not (score >= s2 and time_used <= t2 + 1e-12):
            keep.append((s2, t2))
    keep.append((score, time_used))
    existing[:] = keep
    return True

def evaluate_sequence(total_score, total_time):
    if total_time <= 0:
        return (-1e18, -1e18, -1e18)
    return (total_score / total_time, total_score, -total_time)

def choose_best_tail_target(graph, scores, current_node, current_facing, remaining_treasures, remaining_time):
    best = None
    for t in sorted(remaining_treasures):
        path = bfs_path(graph, current_node, t)
        if not path:
            continue
        move_t, end_node, end_facing, touched = move_time_for_path(graph, path, current_facing)
        if not touched:
            continue
        hit_time = touched[-1][1]
        if hit_time <= remaining_time + 1e-12:
            candidate = (scores[t], -hit_time, t, path, move_t, end_node, end_facing, touched)
            if best is None or candidate > best:
                best = candidate
    return best

def choose_next_treasure_five_step(graph, scores, current_node, current_facing, remaining_treasures,
                                   remaining_time, best_global_score):
    cache_paths = {}
    def get_path(a, b):
        key = (a, b)
        if key not in cache_paths:
            cache_paths[key] = bfs_path(graph, a, b)
        return cache_paths[key]

    best = None
    best_eval = None
    labels = {}

    def dfs(node, facing, rem, depth, acc_score, acc_time, first_choice, visited_order):
        nonlocal best, best_eval

        if acc_time > remaining_time + 1e-12:
            return

        optimistic = acc_score + upper_bound_remaining(scores, rem)
        if optimistic < best_global_score:
            return

        if first_choice is not None:
            cur_eval = evaluate_sequence(acc_score, acc_time)
            if best_eval is None or cur_eval > best_eval:
                best_eval = cur_eval
                best = (first_choice, acc_score, acc_time, list(visited_order))

        if depth == 5 or not rem:
            return

        for t in sorted(rem, key=lambda x: (-scores[x], x)):
            path = get_path(node, t)
            if not path:
                continue

            move_t, end_node, end_facing, touched = move_time_for_path(graph, path, facing)
            if not touched:
                continue

            touch_time = acc_time + touched[-1][1]
            new_score = acc_score + scores[t]
            next_first = first_choice if first_choice is not None else t

            state_key = (t, end_facing, tuple(sorted(rem - {t})), depth + 1)
            label_list = labels.setdefault(state_key, [])
            if not better_label(label_list, new_score, touch_time):
                continue

            dfs(
                end_node,
                end_facing,
                rem - {t},
                depth + 1,
                new_score,
                touch_time,
                next_first,
                visited_order + [t]
            )

    dfs(current_node, current_facing, set(remaining_treasures), 0, 0, 0.0, None, [])
    return best

def plan_route(graph, start_node=START_NODE, start_facing=START_FACING,
               time_limit=RUN_TIME_LIMIT, reserve_seconds=RESERVE_SECONDS,
               tail_switch_seconds=TAIL_SWITCH_SECONDS):
    scores = compute_scores(graph, start_node)
    remaining = set(treasure_nodes(graph, start_node))

    current_node = start_node
    current_facing = start_facing
    used_time = 0.0
    total_score = 0
    treasure_hits = []

    usable_time = time_limit - reserve_seconds

    while remaining:
        remaining_time = usable_time - used_time
        if remaining_time <= 0:
            break

        # New tail rule:
        # when remaining time is less than 9 seconds, compute all reachable remaining treasures,
        # and choose the reachable one with the highest score.
        if remaining_time < tail_switch_seconds:
            tail_choice = choose_best_tail_target(
                graph, scores, current_node, current_facing, remaining, remaining_time
            )
            if tail_choice is None:
                break
            _, _, target, path, move_t, end_node, end_facing, touched = tail_choice
        else:
            choice = choose_next_treasure_five_step(
                graph, scores, current_node, current_facing, remaining,
                remaining_time, total_score
            )
            if choice is None:
                break
            target, _, _, _ = choice
            path = bfs_path(graph, current_node, target)
            move_t, end_node, end_facing, touched = move_time_for_path(graph, path, current_facing)
            if not touched:
                break

        hit_time = used_time + touched[-1][1]
        if hit_time > usable_time + 1e-12:
            break

        used_time = hit_time
        total_score += scores[target]
        treasure_hits.append({
            "treasure": target,
            "score": scores[target],
            "hit_time": round(used_time, 2),
            "cumulative_score": total_score,
        })

        remaining.remove(target)
        current_node = end_node
        current_facing = end_facing

    return {
        "total_score": total_score,
        "used_time": round(used_time, 2),
        "treasure_hits": treasure_hits,
        "scores": scores,
    }

def main():
    parser = argparse.ArgumentParser(description="5-step CP-priority planner with tail rule and 3x score")
    parser.add_argument("--maze", default=MAZE_FILE)
    parser.add_argument("--start", type=int, default=START_NODE)
    parser.add_argument("--start-facing", default=START_FACING, choices=FACINGS)
    parser.add_argument("--time-limit", type=float, default=RUN_TIME_LIMIT)
    parser.add_argument("--reserve-seconds", type=float, default=RESERVE_SECONDS)
    parser.add_argument("--tail-switch-seconds", type=float, default=TAIL_SWITCH_SECONDS)
    args = parser.parse_args()

    graph = load_graph(args.maze)
    result = plan_route(
        graph,
        start_node=args.start,
        start_facing=args.start_facing,
        time_limit=args.time_limit,
        reserve_seconds=args.reserve_seconds,
        tail_switch_seconds=args.tail_switch_seconds,
    )

    print("=== Updated 5-step planner ===")
    print(f"Used time   : {result['used_time']:.2f}s")
    print(f"Total score : {result['total_score']}")
    print("Treasure timeline:")
    for item in result["treasure_hits"]:
        print(
            f"  t={item['hit_time']:.2f}s  "
            f"treasure={item['treasure']:>2}  "
            f"score+={item['score']:>3}  "
            f"cum={item['cumulative_score']:>4}"
        )

if __name__ == "__main__":
    main()
