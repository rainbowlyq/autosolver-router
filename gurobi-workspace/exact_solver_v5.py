"""
Exact solver v5: iterative column-pool MILP heuristic.

This script is intentionally for the offline Python 3.12/Gurobi workspace, not
for the contest runtime.  It builds a restricted set-packing MILP whose columns
are "one task bundle assigned to a fixed courier subset".  The column pool is
grown iteratively:

1. Start with all singleton courier columns plus one short greedy chain.
2. Solve the LP relaxation to obtain dual prices.
3. Generate directed columns with negative reduced cost by greedily extending
   promising seeds under those dual prices.
4. Solve the current integer master to update the incumbent.
5. Add local-neighborhood columns around the incumbent and repeat until the
   pool stalls, the solution stops improving, or the time budget is consumed.

The method is still heuristic for the original nonlinear subset problem, but it
is much less blind than one-shot enumeration.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB


PENALTY_SCORE = 100.0


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_input(input_text):
    lines = input_text.strip().splitlines()
    start = 1 if lines and lines[0].startswith("task_id_list") else 0

    raw = []
    for line in lines[start:]:
        parts = line.strip().split("\t")
        if len(parts) < 4:
            continue
        task_id_list, courier_id, score_txt, will_txt = parts[:4]
        try:
            total_score = float(score_txt)
            willingness = float(will_txt)
        except ValueError:
            continue
        task_id_list = task_id_list.strip()
        courier_id = courier_id.strip()
        task_ids = tuple(t.strip() for t in task_id_list.split(",") if t.strip())
        if not task_ids or not courier_id:
            continue
        raw.append((task_id_list, task_ids, courier_id, total_score, willingness))

    bundle_map = {}
    bundles = {}
    bundle_labels = {}
    for task_id_list, task_ids, _, _, _ in raw:
        if task_id_list not in bundle_map:
            bid = len(bundle_map)
            bundle_map[task_id_list] = bid
            bundles[bid] = task_ids
            bundle_labels[bid] = task_id_list

    candidates = [
        (bundle_map[task_id_list], courier_id, score, willingness)
        for task_id_list, _, courier_id, score, willingness in raw
    ]
    all_tasks = sorted({t for task_ids in bundles.values() for t in task_ids})
    all_couriers = sorted({c[1] for c in candidates})

    return bundles, bundle_labels, candidates, all_tasks, all_couriers


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def _bundle_cost_for_couriers(couriers, n_tasks):
    """Exact evaluator-compatible cost for a set of (score, p) tuples."""
    if not couriers:
        return 0.0

    miss = 1.0
    total_p = 0.0
    weighted_score_numerator = 0.0
    for score, p in couriers:
        p = min(max(p, 0.0), 1.0)
        miss *= 1.0 - p
        total_p += p
        weighted_score_numerator += score * p

    if total_p <= 0.0:
        return PENALTY_SCORE * n_tasks

    p_complete = 1.0 - miss
    expected_score = weighted_score_numerator / total_p
    return (
        p_complete * expected_score
        + (1.0 - p_complete) * PENALTY_SCORE * n_tasks
    )


def _column_cost(bundle_cand_data, bid, idx_set, bundle_size_map):
    couriers = [
        (bundle_cand_data[bid][ci][1], bundle_cand_data[bid][ci][2])
        for ci in idx_set
    ]
    return _bundle_cost_for_couriers(couriers, bundle_size_map[bid])


def _marginal_delta(existing_couriers, new_courier, n_tasks):
    old_cost = _bundle_cost_for_couriers(existing_couriers, n_tasks)
    new_cost = _bundle_cost_for_couriers(existing_couriers + [new_courier], n_tasks)
    return new_cost - old_cost


# ---------------------------------------------------------------------------
# Column pool helpers
# ---------------------------------------------------------------------------

def _add_column(bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map, bid, idx_set):
    key = tuple(sorted(set(idx_set)))
    if not key:
        return False
    if key in bundle_seen[bid]:
        return False
    cost = _column_cost(bundle_cand_data, bid, key, bundle_size_map)
    bundle_seen[bid].add(key)
    bundle_columns[bid].append((key, cost))
    return True


def _initialize_columns(bundle_cand_data, bundle_size_map, n_bundles, max_greedy_size=4):
    bundle_columns = {bid: [] for bid in range(n_bundles)}
    bundle_seen = {bid: set() for bid in range(n_bundles)}

    for bid in range(n_bundles):
        courier_list = bundle_cand_data[bid]
        n = len(courier_list)
        if n == 0:
            continue

        best_single = None
        best_net = float("inf")
        for i, (_, score, p) in enumerate(courier_list):
            _add_column(bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map, bid, (i,))
            cost = _bundle_cost_for_couriers([(score, p)], bundle_size_map[bid])
            net = cost - PENALTY_SCORE * bundle_size_map[bid]
            if net < best_net:
                best_net = net
                best_single = i

        if best_single is None:
            continue

        current = [best_single]
        current_couriers = [(courier_list[best_single][1], courier_list[best_single][2])]
        for _ in range(min(max_greedy_size - 1, n - 1)):
            best_add = None
            best_delta = 0.0
            used = set(current)
            for i, (_, score, p) in enumerate(courier_list):
                if i in used:
                    continue
                delta = _marginal_delta(current_couriers, (score, p), bundle_size_map[bid])
                if delta < best_delta:
                    best_delta = delta
                    best_add = i
            if best_add is None:
                break
            current.append(best_add)
            current_couriers.append((courier_list[best_add][1], courier_list[best_add][2]))
            _add_column(bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map, bid, current)

    return bundle_columns, bundle_seen


def _column_objective_coeff(cost, bid, bundle_size_map):
    return cost - PENALTY_SCORE * bundle_size_map[bid]


def _column_reduced_cost(
    bid,
    idx_set,
    cost,
    bundle_cand_data,
    bundle_size_map,
    bundles,
    dual_bundle,
    dual_courier,
    dual_task,
):
    rc = _column_objective_coeff(cost, bid, bundle_size_map)
    rc -= dual_bundle.get(bid, 0.0)
    for task_id in bundles[bid]:
        rc -= dual_task.get(task_id, 0.0)
    for ci in idx_set:
        cid = bundle_cand_data[bid][ci][0]
        rc -= dual_courier.get(cid, 0.0)
    return rc


def _build_usage_maps(bundle_columns, bundle_cand_data, bundles):
    courier_columns = defaultdict(list)
    task_columns = defaultdict(list)

    for bid, columns in bundle_columns.items():
        for col_idx, (idx_set, _) in enumerate(columns):
            for ci in idx_set:
                cid = bundle_cand_data[bid][ci][0]
                courier_columns[cid].append((bid, col_idx))
            for task_id in bundles[bid]:
                task_columns[task_id].append((bid, col_idx))

    return courier_columns, task_columns


# ---------------------------------------------------------------------------
# Master problem
# ---------------------------------------------------------------------------

def _solve_master(
    bundle_columns,
    bundle_cand_data,
    bundles,
    all_tasks,
    all_couriers,
    bundle_size_map,
    time_limit,
    mip_gap,
    relax=False,
    incumbent_cutoff=None,
):
    model_name = "column_lp" if relax else "column_mip"
    m = gp.Model(model_name)
    m.Params.OutputFlag = 0
    if time_limit is not None:
        m.Params.TimeLimit = max(1.0, float(time_limit))
    if not relax:
        m.Params.MIPGap = mip_gap
        m.Params.MIPFocus = 1
        if incumbent_cutoff is not None and math.isfinite(incumbent_cutoff):
            m.Params.Cutoff = incumbent_cutoff - PENALTY_SCORE * len(all_tasks) + 1e-7

    vtype = GRB.CONTINUOUS if relax else GRB.BINARY
    z = {}
    for bid, columns in bundle_columns.items():
        for col_idx, (_, cost) in enumerate(columns):
            obj = _column_objective_coeff(cost, bid, bundle_size_map)
            z[(bid, col_idx)] = m.addVar(lb=0.0, ub=1.0, obj=obj, vtype=vtype)

    m.ModelSense = GRB.MINIMIZE
    m.update()

    constr_bundle = {}
    for bid, columns in bundle_columns.items():
        expr = gp.quicksum(z[(bid, col_idx)] for col_idx in range(len(columns)))
        constr_bundle[bid] = m.addConstr(expr <= 1.0, name=f"bundle_{bid}")

    courier_columns, task_columns = _build_usage_maps(bundle_columns, bundle_cand_data, bundles)

    constr_courier = {}
    for cid in all_couriers:
        entries = courier_columns.get(cid, ())
        expr = gp.quicksum(z[(bid, col_idx)] for bid, col_idx in entries)
        constr_courier[cid] = m.addConstr(expr <= 1.0, name=f"courier_{cid}")

    constr_task = {}
    for task_id in all_tasks:
        entries = task_columns.get(task_id, ())
        expr = gp.quicksum(z[(bid, col_idx)] for bid, col_idx in entries)
        constr_task[task_id] = m.addConstr(expr <= 1.0, name=f"task_{task_id}")

    m.optimize()

    const_offset = PENALTY_SCORE * len(all_tasks)

    if relax:
        if m.Status != GRB.OPTIMAL:
            return None
        duals = {
            "bundle": {bid: constr.Pi for bid, constr in constr_bundle.items()},
            "courier": {cid: constr.Pi for cid, constr in constr_courier.items()},
            "task": {task_id: constr.Pi for task_id, constr in constr_task.items()},
            "objective": m.ObjVal + const_offset,
        }
        return duals

    if m.SolCount == 0:
        return None, float("inf"), None

    solution = {}
    for bid, columns in bundle_columns.items():
        for col_idx, (idx_set, cost) in enumerate(columns):
            var = z[(bid, col_idx)]
            if var.X > 0.5:
                solution[bid] = (idx_set, cost)
                break

    return solution, m.ObjVal + const_offset, m


# ---------------------------------------------------------------------------
# Directed column generation
# ---------------------------------------------------------------------------

def _greedy_extend_seed(
    bid,
    seed,
    bundle_cand_data,
    bundle_size_map,
    bundles,
    dual_bundle,
    dual_courier,
    dual_task,
    max_size,
):
    current = tuple(sorted(set(seed)))
    if not current:
        return []

    generated = []
    cost = _column_cost(bundle_cand_data, bid, current, bundle_size_map)
    rc = _column_reduced_cost(
        bid, current, cost, bundle_cand_data, bundle_size_map,
        bundles, dual_bundle, dual_courier, dual_task,
    )

    while len(current) < min(max_size, len(bundle_cand_data[bid])):
        best_next = None
        best_cost = None
        best_rc = rc
        used = set(current)
        for i in range(len(bundle_cand_data[bid])):
            if i in used:
                continue
            trial = tuple(sorted(current + (i,)))
            trial_cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
            trial_rc = _column_reduced_cost(
                bid, trial, trial_cost, bundle_cand_data, bundle_size_map,
                bundles, dual_bundle, dual_courier, dual_task,
            )
            if trial_rc < best_rc - 1e-8:
                best_next = trial
                best_cost = trial_cost
                best_rc = trial_rc

        if best_next is None:
            break
        current = best_next
        cost = best_cost
        rc = best_rc
        generated.append((rc, bid, current, cost, "dual_grow"))

    return generated


def _seed_indices_for_bundle(bid, bundle_cand_data, bundle_size_map, bundles, duals, seed_count):
    dual_bundle = duals["bundle"]
    dual_courier = duals["courier"]
    dual_task = duals["task"]
    scored = []
    for i, (_, score, p) in enumerate(bundle_cand_data[bid]):
        cost = _bundle_cost_for_couriers([(score, p)], bundle_size_map[bid])
        rc = _column_reduced_cost(
            bid, (i,), cost, bundle_cand_data, bundle_size_map,
            bundles, dual_bundle, dual_courier, dual_task,
        )
        net = cost - PENALTY_SCORE * bundle_size_map[bid]
        scored.append((rc, net, -p, score, i))

    scored.sort()
    seeds = [i for _, _, _, _, i in scored[:seed_count]]

    by_p = sorted(range(len(bundle_cand_data[bid])), key=lambda i: bundle_cand_data[bid][i][2], reverse=True)
    for i in by_p[: max(2, seed_count // 2)]:
        if i not in seeds:
            seeds.append(i)

    return seeds


def _price_columns(
    bundle_columns,
    bundle_seen,
    bundle_cand_data,
    bundle_size_map,
    bundles,
    duals,
    max_size=8,
    seed_count=8,
    per_bundle_limit=12,
    total_limit=6000,
    rc_threshold=-1e-7,
):
    dual_bundle = duals["bundle"]
    dual_courier = duals["courier"]
    dual_task = duals["task"]
    candidates = []

    for bid in range(len(bundles)):
        n = len(bundle_cand_data[bid])
        if n <= 1:
            continue

        local = []
        seeds = _seed_indices_for_bundle(
            bid, bundle_cand_data, bundle_size_map, bundles, duals, seed_count
        )

        for seed in seeds:
            local.extend(
                _greedy_extend_seed(
                    bid, (seed,), bundle_cand_data, bundle_size_map, bundles,
                    dual_bundle, dual_courier, dual_task, max_size,
                )
            )

        seed_pool = seeds[: min(len(seeds), 10)]
        for r in (2, 3):
            if len(seed_pool) < r:
                continue
            for combo in itertools.combinations(seed_pool, r):
                idx_set = tuple(sorted(combo))
                if idx_set in bundle_seen[bid]:
                    continue
                cost = _column_cost(bundle_cand_data, bid, idx_set, bundle_size_map)
                rc = _column_reduced_cost(
                    bid, idx_set, cost, bundle_cand_data, bundle_size_map,
                    bundles, dual_bundle, dual_courier, dual_task,
                )
                local.append((rc, bid, idx_set, cost, f"dual_combo_{r}"))

        local = [
            item for item in local
            if item[2] not in bundle_seen[item[1]] and item[0] < rc_threshold
        ]
        local.sort(key=lambda x: x[0])
        candidates.extend(local[:per_bundle_limit])

    candidates.sort(key=lambda x: x[0])
    return candidates[:total_limit]


def _incumbent_neighborhood_columns(
    solution,
    bundle_seen,
    bundle_cand_data,
    bundle_size_map,
    max_size=10,
    per_bundle_limit=8,
):
    if not solution:
        return []

    generated = []
    for bid, (idx_set, _) in solution.items():
        current = tuple(sorted(idx_set))
        current_cost = _column_cost(bundle_cand_data, bid, current, bundle_size_map)
        local = []

        used = set(current)
        for i in range(len(bundle_cand_data[bid])):
            if i in used or len(current) >= max_size:
                continue
            trial = tuple(sorted(current + (i,)))
            if trial in bundle_seen[bid]:
                continue
            cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
            if cost < current_cost - 1e-8:
                local.append((cost - current_cost, bid, trial, cost, "incumbent_add"))

        for drop in current:
            base = tuple(i for i in current if i != drop)
            for add in range(len(bundle_cand_data[bid])):
                if add in used:
                    continue
                trial = tuple(sorted(base + (add,)))
                if not trial or trial in bundle_seen[bid]:
                    continue
                cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
                if cost < current_cost - 1e-8:
                    local.append((cost - current_cost, bid, trial, cost, "incumbent_swap"))

        local.sort(key=lambda x: x[0])
        generated.extend(local[:per_bundle_limit])

    generated.sort(key=lambda x: x[0])
    return generated


def _add_generated_columns(generated, bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map):
    added = 0
    by_source = defaultdict(int)
    for _, bid, idx_set, _, source in generated:
        if _add_column(bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map, bid, idx_set):
            added += 1
            by_source[source] += 1
    return added, dict(sorted(by_source.items()))


def _column_count(bundle_columns):
    return sum(len(cols) for cols in bundle_columns.values())


# ---------------------------------------------------------------------------
# Local improvement and validation helpers
# ---------------------------------------------------------------------------

def _local_improve(solution, bundle_cand_data, bundle_size_map):
    """Greedily add, remove, and swap couriers within selected bundles."""
    if not solution:
        return {}

    assigned = set()
    bundle_idx_sets = {}
    for bid, (idx_set, _) in solution.items():
        idx_set = set(idx_set)
        bundle_idx_sets[bid] = idx_set
        for ci in idx_set:
            assigned.add(bundle_cand_data[bid][ci][0])

    improved = True
    while improved:
        improved = False
        for bid in list(bundle_idx_sets.keys()):
            current = set(bundle_idx_sets[bid])
            current_tuple = tuple(sorted(current))
            current_cost = _column_cost(bundle_cand_data, bid, current_tuple, bundle_size_map)

            best_action = None
            best_delta = 0.0

            # Add an unused courier.
            for ci in range(len(bundle_cand_data[bid])):
                cid = bundle_cand_data[bid][ci][0]
                if ci in current or cid in assigned:
                    continue
                trial = tuple(sorted(current | {ci}))
                cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
                delta = cost - current_cost
                if delta < best_delta - 1e-9:
                    best_delta = delta
                    best_action = ("add", ci, None)

            # Remove a courier if the group got worse by including it.
            if len(current) > 1:
                for ci in tuple(current):
                    trial_set = set(current)
                    trial_set.remove(ci)
                    trial = tuple(sorted(trial_set))
                    cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
                    delta = cost - current_cost
                    if delta < best_delta - 1e-9:
                        best_delta = delta
                        best_action = ("remove", ci, None)

            # Swap one assigned courier for one globally unused courier.
            for drop in tuple(current):
                for add in range(len(bundle_cand_data[bid])):
                    add_cid = bundle_cand_data[bid][add][0]
                    if add in current or add_cid in assigned:
                        continue
                    trial_set = set(current)
                    trial_set.remove(drop)
                    trial_set.add(add)
                    trial = tuple(sorted(trial_set))
                    cost = _column_cost(bundle_cand_data, bid, trial, bundle_size_map)
                    delta = cost - current_cost
                    if delta < best_delta - 1e-9:
                        best_delta = delta
                        best_action = ("swap", add, drop)

            if best_action is None:
                continue

            kind, add_ci, drop_ci = best_action
            if kind == "add":
                current.add(add_ci)
                assigned.add(bundle_cand_data[bid][add_ci][0])
            elif kind == "remove":
                current.remove(add_ci)
                assigned.remove(bundle_cand_data[bid][add_ci][0])
            else:
                current.remove(drop_ci)
                assigned.remove(bundle_cand_data[bid][drop_ci][0])
                current.add(add_ci)
                assigned.add(bundle_cand_data[bid][add_ci][0])
            bundle_idx_sets[bid] = current
            improved = True

    improved_solution = {}
    for bid, idx_set in bundle_idx_sets.items():
        key = tuple(sorted(idx_set))
        if key:
            improved_solution[bid] = (
                key,
                _column_cost(bundle_cand_data, bid, key, bundle_size_map),
            )
    return improved_solution


def _compute_total_cost(solution, bundle_cand_data, bundle_size_map, all_tasks, bundles):
    total_cost = 0.0
    assigned_tasks = set()
    used_couriers = set()
    valid = True

    for bid, (indices, _) in solution.items():
        total_cost += _column_cost(bundle_cand_data, bid, indices, bundle_size_map)
        assigned_tasks.update(bundles[bid])
        for ci in indices:
            cid = bundle_cand_data[bid][ci][0]
            if cid in used_couriers:
                valid = False
            used_couriers.add(cid)

    unassigned = len(set(all_tasks) - assigned_tasks)
    total_cost += unassigned * PENALTY_SCORE
    return total_cost, unassigned, valid


def _prepare_bundle_candidate_data(candidates, n_bundles, bundle_size_map):
    best_by_bundle_courier = {}
    for bid, cid, score, will in candidates:
        p = min(max(will, 0.0), 1.0)
        key = (bid, cid)
        # The contest output format only names (task_id_list, courier_id), so it
        # cannot disambiguate duplicate input rows.  Keep the first row, matching
        # the local benchmark reconstruction logic, instead of optimizing against
        # a duplicate row that cannot be selected explicitly in the output.
        if key not in best_by_bundle_courier:
            best_by_bundle_courier[key] = (score, p)

    bundle_cand_data = {bid: [] for bid in range(n_bundles)}
    for (bid, cid), (score, p) in best_by_bundle_courier.items():
        bundle_cand_data[bid].append((cid, score, p))

    for bid in range(n_bundles):
        bundle_cand_data[bid].sort(key=lambda item: (
            _bundle_cost_for_couriers([(item[1], item[2])], bundle_size_map[bid]),
            -item[2],
            item[0],
        ))

    return bundle_cand_data


def _format_output(result):
    return "\n".join(
        f"{task_id_list}\t{','.join(courier_ids)}"
        for task_id_list, courier_ids in result
    )


# ---------------------------------------------------------------------------
# Main solve
# ---------------------------------------------------------------------------

def solve_exact(
    input_text,
    time_limit=600.0,
    mip_gap=1e-6,
    max_iterations=18,
    stall_iterations=4,
    min_round_seconds=30.0,
    verbose=True,
    return_stats=False,
):
    t0 = time.time()
    stats = {
        "iterations": 0,
        "stop_reason": "",
        "initial_columns": 0,
        "final_columns": 0,
        "best_cost": float("inf"),
        "final_cost": float("inf"),
        "unassigned_count": 0,
        "total_seconds": 0.0,
        "local_improvement_seconds": 0.0,
    }

    bundles, bundle_labels, candidates, all_tasks, all_couriers = parse_input(input_text)
    n_bundles = len(bundles)
    n_tasks = len(all_tasks)
    bundle_size_map = {bid: len(task_ids) for bid, task_ids in bundles.items()}

    if n_tasks == 0 or n_bundles == 0:
        stats.update({
            "stop_reason": "empty_input",
            "best_cost": 0.0,
            "final_cost": 0.0,
            "total_seconds": time.time() - t0,
        })
        return ([], stats) if return_stats else []

    bundle_cand_data = _prepare_bundle_candidate_data(candidates, n_bundles, bundle_size_map)
    all_couriers = sorted({cid for rows in bundle_cand_data.values() for cid, _, _ in rows})

    if verbose:
        print(
            f"Parsed: {n_tasks} tasks, {len(all_couriers)} couriers, "
            f"{n_bundles} bundles, {len(candidates)} candidates"
        )

    bundle_columns, bundle_seen = _initialize_columns(
        bundle_cand_data, bundle_size_map, n_bundles, max_greedy_size=4
    )
    stats["initial_columns"] = _column_count(bundle_columns)

    best_solution = {}
    best_cost = PENALTY_SCORE * n_tasks
    best_unassigned = n_tasks
    no_improve_rounds = 0

    if verbose:
        print(f"Initial column pool: {_column_count(bundle_columns)} columns")

    for iteration in range(1, max_iterations + 1):
        elapsed = time.time() - t0
        remaining = time_limit - elapsed
        min_required = min(float(min_round_seconds), max(2.0, time_limit * 0.25))
        if remaining <= min_required:
            stats["stop_reason"] = "time_budget_nearly_exhausted"
            if verbose:
                print(
                    "Stopping: time budget nearly exhausted "
                    f"(remaining={remaining:.1f}s, required={min_required:.1f}s)"
                )
            break

        lp_t0 = time.time()
        stats["iterations"] = iteration
        duals = _solve_master(
            bundle_columns, bundle_cand_data, bundles, all_tasks, all_couriers,
            bundle_size_map, time_limit=min(120.0, max(2.0, remaining * 0.25)),
            mip_gap=mip_gap, relax=True,
        )
        if duals is None:
            if verbose:
                print(f"Iteration {iteration}: LP relaxation failed; solving incumbent MIP only")
            duals = {"bundle": {}, "courier": {}, "task": {}, "objective": float("nan")}

        generated = _price_columns(
            bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map,
            bundles, duals, max_size=8, seed_count=8,
            per_bundle_limit=14, total_limit=7000,
        )
        added, by_source = _add_generated_columns(
            generated, bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map
        )

        mip_remaining = max(2.0, time_limit - (time.time() - t0))
        mip_slice = min(mip_remaining, max(15.0, mip_remaining / max(1, max_iterations - iteration + 1)))
        solution, obj_val, model = _solve_master(
            bundle_columns, bundle_cand_data, bundles, all_tasks, all_couriers,
            bundle_size_map, time_limit=mip_slice, mip_gap=mip_gap,
            relax=False, incumbent_cutoff=None,
        )

        improved = False
        if solution is not None:
            cost, unassigned, valid = _compute_total_cost(
                solution, bundle_cand_data, bundle_size_map, all_tasks, bundles
            )
            if valid and cost < best_cost - 1e-7:
                best_solution = solution
                best_cost = cost
                best_unassigned = unassigned
                no_improve_rounds = 0
                improved = True
            else:
                no_improve_rounds += 1
        else:
            no_improve_rounds += 1
            cost = float("inf")
            unassigned = n_tasks

        neighborhood = _incumbent_neighborhood_columns(
            best_solution, bundle_seen, bundle_cand_data, bundle_size_map,
            max_size=10, per_bundle_limit=8,
        )
        added_neighborhood, by_neighborhood = _add_generated_columns(
            neighborhood, bundle_columns, bundle_seen, bundle_cand_data, bundle_size_map
        )
        added_total = added + added_neighborhood

        if verbose:
            status = model.Status if model is not None else "none"
            gap = model.MIPGap if model is not None and model.SolCount > 0 else float("nan")
            lp_obj = duals.get("objective", float("nan"))
            print(
                "Iteration {0}: cols={1}, added={2}+{3}, lp={4:.4f}, "
                "mip={5:.4f}, best={6:.4f}, unassigned={7}, gap={8:.4g}, "
                "status={9}, improved={10}, lp_time={11:.1f}s".format(
                    iteration, _column_count(bundle_columns), added,
                    added_neighborhood, lp_obj, cost, best_cost,
                    best_unassigned, gap, status, improved, time.time() - lp_t0,
                )
            )
            if by_source or by_neighborhood:
                print(f"  added_by_source={by_source}, neighborhood={by_neighborhood}")

        if added_total == 0:
            stats["stop_reason"] = "no_new_directed_columns"
            if verbose:
                print("Stopping: no new directed columns")
            break
        if no_improve_rounds >= stall_iterations and added_total < 25:
            stats["stop_reason"] = "stalled"
            if verbose:
                print(f"Stopping: stalled for {no_improve_rounds} iterations")
            break
    else:
        stats["stop_reason"] = "max_iterations"

    if verbose:
        print("Final local improvement...")
    local_t0 = time.time()
    improved_solution = _local_improve(best_solution, bundle_cand_data, bundle_size_map)
    stats["local_improvement_seconds"] = time.time() - local_t0
    improved_cost, improved_unassigned, valid = _compute_total_cost(
        improved_solution, bundle_cand_data, bundle_size_map, all_tasks, bundles
    )
    if valid and improved_cost <= best_cost + 1e-7:
        best_solution = improved_solution
        best_cost = improved_cost
        best_unassigned = improved_unassigned

    if verbose:
        print(f"Total time: {time.time() - t0:.1f}s")
        print(f"Final cost: {best_cost:.6f}, unassigned={best_unassigned}")

    stats.update({
        "final_columns": _column_count(bundle_columns),
        "best_cost": best_cost,
        "final_cost": best_cost,
        "unassigned_count": best_unassigned,
        "total_seconds": time.time() - t0,
    })
    if not stats["stop_reason"]:
        stats["stop_reason"] = "completed"

    result = []
    for bid in sorted(best_solution):
        indices, _ = best_solution[bid]
        courier_ids = [bundle_cand_data[bid][ci][0] for ci in indices]
        result.append((bundle_labels[bid], courier_ids))

    return (result, stats) if return_stats else result


def solve_file(input_path, output_path=None, **kwargs):
    input_path = Path(input_path)
    input_text = input_path.read_text(encoding="utf-8")
    return_stats = kwargs.get("return_stats", False)
    solved = solve_exact(input_text, **kwargs)
    if return_stats:
        output, stats = solved
    else:
        output, stats = solved, None
    output_text = _format_output(output)
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + ("\n" if output_text else ""), encoding="utf-8")
    return (output, stats) if return_stats else output


def batch_solve(
    input_dir,
    output_dir,
    time_limit=600.0,
    mip_gap=1e-6,
    max_iterations=10,
    stall_iterations=3,
    min_round_seconds=30.0,
):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    case_files = sorted(input_dir.glob("*.txt"))
    rows = []

    for idx, case_path in enumerate(case_files, 1):
        print(f"\n=== [{idx}/{len(case_files)}] {case_path.name} ===")
        t0 = time.time()
        out_path = output_dir / case_path.name
        output, stats = solve_file(
            case_path, out_path, time_limit=time_limit, mip_gap=mip_gap,
            max_iterations=max_iterations, stall_iterations=stall_iterations,
            min_round_seconds=min_round_seconds,
            verbose=True,
            return_stats=True,
        )
        elapsed = time.time() - t0
        rows.append({
            "case_file": case_path.name,
            "output_file": out_path.name,
            "assignments": len(output),
            "iterations": stats["iterations"],
            "stop_reason": stats["stop_reason"],
            "best_cost": f"{stats['final_cost']:.12f}",
            "unassigned_count": stats["unassigned_count"],
            "initial_columns": stats["initial_columns"],
            "final_columns": stats["final_columns"],
            "solver_seconds": f"{stats['total_seconds']:.3f}",
            "local_improvement_seconds": f"{stats['local_improvement_seconds']:.3f}",
            "elapsed_seconds": f"{elapsed:.3f}",
        })
        print(f"Saved: {out_path} ({len(output)} assignments, {elapsed:.1f}s)")

    summary_path = output_dir / "summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_file",
                "output_file",
                "assignments",
                "iterations",
                "stop_reason",
                "best_cost",
                "unassigned_count",
                "initial_columns",
                "final_columns",
                "solver_seconds",
                "local_improvement_seconds",
                "elapsed_seconds",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSummary: {summary_path}")
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Offline iterative Gurobi reference solver.")
    parser.add_argument("input_file", nargs="?", help="single input TSV file")
    parser.add_argument("time_limit_s", nargs="?", type=float, default=600.0)
    parser.add_argument("--time-limit", type=float, default=None, help="per-case solve time limit")
    parser.add_argument("--output", "-o", help="write single-case TSV output here")
    parser.add_argument("--batch-dir", help="solve all *.txt files from this directory")
    parser.add_argument("--output-dir", default=None, help="batch output directory")
    parser.add_argument("--mip-gap", type=float, default=1e-6)
    parser.add_argument("--max-iterations", type=int, default=18)
    parser.add_argument("--stall-iterations", type=int, default=4)
    parser.add_argument("--min-round-seconds", type=float, default=30.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    time_limit = args.time_limit if args.time_limit is not None else args.time_limit_s

    if args.batch_dir:
        if not args.output_dir:
            raise SystemExit("--output-dir is required with --batch-dir")
        batch_solve(
            args.batch_dir,
            args.output_dir,
            time_limit,
            args.mip_gap,
            args.max_iterations,
            args.stall_iterations,
            args.min_round_seconds,
        )
        return

    if not args.input_file:
        parser.print_usage()
        raise SystemExit(1)

    output = solve_file(
        args.input_file, args.output, time_limit=time_limit,
        mip_gap=args.mip_gap, max_iterations=args.max_iterations,
        stall_iterations=args.stall_iterations,
        min_round_seconds=args.min_round_seconds, verbose=not args.quiet,
    )

    if args.output:
        print(f"Saved: {args.output} ({len(output)} assignments)")
    elif output:
        print(f"\nOutput ({len(output)} assignments):")
        print(_format_output(output))
    else:
        print("No solution found.")


if __name__ == "__main__":
    main(sys.argv[1:])
