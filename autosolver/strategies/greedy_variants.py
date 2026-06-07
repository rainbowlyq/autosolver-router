from collections import defaultdict
import heapq
from typing import Optional

from autosolver.budget import TimeBudget
from autosolver.evaluator import (
    PENALTY_SCORE,
    _group_assignment_cost,
    candidate_assignment_cost,
    is_better_solution,
)
from autosolver.models import Assignment, Candidate, ProblemInstance, Solution


def _safe_willingness(candidate: Candidate) -> float:
    return max(candidate.willingness, 0.01)


def _build_unique_task_package_solution(
    ordered_candidates,
    budget: TimeBudget,
) -> Solution:
    used_couriers = set()
    used_task_packages = set()
    used_tasks = set()
    assignments = []

    for candidate in ordered_candidates:
        if budget.expired():
            break
        if candidate.courier_id in used_couriers:
            continue
        if candidate.task_id_list in used_task_packages:
            continue
        if any(task_id in used_tasks for task_id in candidate.task_ids):
            continue

        assignments.append(Assignment.from_candidate(candidate))
        used_couriers.add(candidate.courier_id)
        used_task_packages.add(candidate.task_id_list)
        used_tasks.update(candidate.task_ids)

    return Solution(assignments=tuple(assignments))


class GreedyByExpectedScore:
    name = "greedy_by_expected_score"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        ordered = sorted(
            instance.candidates,
            key=lambda candidate: (
                candidate.total_score / _safe_willingness(candidate),
                candidate.total_score,
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            ),
        )
        return _build_unique_task_package_solution(ordered, budget)


class GreedyByCoverage:
    name = "greedy_by_coverage"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        ordered = sorted(
            instance.candidates,
            key=lambda candidate: (
                -len(candidate.task_ids),
                candidate.total_score / len(candidate.task_ids),
                candidate.total_score,
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            ),
        )
        return _build_unique_task_package_solution(ordered, budget)


class GreedyCoverageAware:
    name = "greedy_coverage_aware"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        candidates_by_size = defaultdict(list)
        for candidate in instance.candidates:
            candidates_by_size[len(candidate.task_ids)].append(candidate)

        for size in candidates_by_size:
            candidates_by_size[size].sort(
                key=lambda candidate: (
                    candidate_assignment_cost(candidate),
                    candidate.task_id_list,
                    candidate.courier_id,
                    candidate.index,
                )
            )

        used_couriers = set()
        covered_tasks = set()
        assignments = []

        for size in sorted(candidates_by_size.keys(), reverse=True):
            if budget.expired():
                break
            for candidate in candidates_by_size[size]:
                if budget.expired():
                    break
                if candidate.courier_id in used_couriers:
                    continue
                candidate_tasks = set(candidate.task_ids)
                if not candidate_tasks & covered_tasks:
                    assignments.append(Assignment.from_candidate(candidate))
                    used_couriers.add(candidate.courier_id)
                    covered_tasks.update(candidate_tasks)

        return Solution(assignments=tuple(assignments))


class MarginalSavingsGreedy:
    name = "marginal_savings_greedy"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        used_couriers = set()
        task_package_by_task = {}
        task_groups = {}
        assignments = []

        while not budget.expired():
            best_candidate = None
            best_saving = 0.0

            for candidate in instance.candidates:
                if candidate.courier_id in used_couriers:
                    continue

                group = task_groups.get(candidate.task_id_list)
                if group is not None:
                    saving = _group_assignment_cost(group) - _group_assignment_cost(group + [candidate])
                else:
                    conflicts = False
                    for task_id in candidate.task_ids:
                        if task_id in task_package_by_task:
                            conflicts = True
                            break
                    if conflicts:
                        continue
                    saving = (
                        PENALTY_SCORE * len(candidate.task_ids)
                        - candidate_assignment_cost(candidate)
                    )

                if saving > best_saving:
                    best_saving = saving
                    best_candidate = candidate

            if best_candidate is None:
                break

            assignments.append(Assignment.from_candidate(best_candidate))
            used_couriers.add(best_candidate.courier_id)
            task_groups.setdefault(best_candidate.task_id_list, []).append(best_candidate)
            for task_id in best_candidate.task_ids:
                task_package_by_task[task_id] = best_candidate.task_id_list

        return Solution(assignments=tuple(assignments))


class PressureCoverageGreedy:
    name = "pressure_coverage_greedy"

    def __init__(
        self,
        max_variants=None,
        max_candidates: int = 12000,
        min_couriers: int = 26,
    ) -> None:
        self.max_variants = max_variants
        self.max_candidates = max_candidates
        self.min_couriers = min_couriers

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        if not instance.candidates:
            return Solution.empty()
        if len(instance.candidates) > self.max_candidates:
            return incumbent or Solution.empty()
        if len(instance.courier_ids) < self.min_couriers:
            return incumbent or Solution.empty()

        pressures = _build_task_pressures(instance)
        candidate_costs = {
            candidate.index: candidate_assignment_cost(candidate)
            for candidate in instance.candidates
        }
        variants = (
            (16.0, 0.5),
            (8.0, 4.0),
            (16.0, 2.0),
            (1.0, 4.0),
            (2.0, 2.0),
            (32.0, 1.0),
            (1.0, 0.0),
            (0.0, 0.0),
        )
        if self.max_variants is not None:
            variants = variants[: self.max_variants]

        best = incumbent or Solution.empty()
        for alpha, beta in variants:
            if budget.expired():
                break
            candidate_solution = _run_pressure_variant(
                instance,
                budget,
                pressures,
                candidate_costs,
                alpha,
                beta,
            )
            if candidate_solution.assignments and not budget.expired():
                candidate_solution = ReinforceGreedy().run(instance, candidate_solution, budget)
            if is_better_solution(instance, candidate_solution, best):
                best = candidate_solution

        return best


class BeamSetPackingSearch:
    name = "beam_set_packing_search"

    def __init__(
        self,
        variants=None,
        max_tasks: int = 45,
        max_couriers: int = 25,
    ) -> None:
        self.variants = variants or (
            (1000, 80, 100.0, "cost", "unit"),
            (2000, 120, 100.0, "id", "unit"),
        )
        self.max_tasks = max_tasks
        self.max_couriers = max_couriers

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        if (
            not instance.candidates
            or len(instance.task_ids) > self.max_tasks
            or len(instance.courier_ids) > self.max_couriers
        ):
            return incumbent or Solution.empty()
        if not any(len(candidate.task_ids) > 1 for candidate in instance.candidates):
            return incumbent or Solution.empty()

        task_index_by_id = {
            task_id: task_index
            for task_index, task_id in enumerate(instance.task_ids)
        }
        candidates_by_courier = defaultdict(list)
        for candidate in instance.candidates:
            task_mask = 0
            for task_id in candidate.task_ids:
                task_mask |= 1 << task_index_by_id[task_id]
            cost = candidate_assignment_cost(candidate)
            candidates_by_courier[candidate.courier_id].append(
                (
                    cost,
                    task_mask,
                    candidate,
                )
            )

        best = incumbent or Solution.empty()
        for variant in self.variants:
            if budget.expired():
                break
            candidate_solution = _run_beam_variant(
                instance,
                budget,
                candidates_by_courier,
                variant,
            )
            if is_better_solution(instance, candidate_solution, best):
                best = candidate_solution

        if best.assignments and not budget.expired():
            reinforced = ReinforceGreedy().run(instance, best, budget)
            if is_better_solution(instance, reinforced, best):
                best = reinforced
        return best


class SingletonBeamReassignment:
    name = "singleton_beam_reassignment"

    def __init__(
        self,
        beam_width: int = 500,
        max_tasks: int = 20,
        max_couriers: int = 30,
    ) -> None:
        self.beam_width = max(1, beam_width)
        self.max_tasks = max_tasks
        self.max_couriers = max_couriers

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        best = incumbent or Solution.empty()
        if (
            not instance.candidates
            or len(instance.task_ids) > self.max_tasks
            or len(instance.courier_ids) > self.max_couriers
            or any(len(candidate.task_ids) > 1 for candidate in instance.candidates)
        ):
            return best

        task_index_by_id = {
            task_id: task_index
            for task_index, task_id in enumerate(instance.task_ids)
        }
        candidates_by_courier = defaultdict(list)
        for candidate in instance.candidates:
            if len(candidate.task_ids) == 1:
                candidates_by_courier[candidate.courier_id].append(candidate)

        courier_groups = []
        for courier_id in instance.courier_ids:
            candidates = sorted(
                candidates_by_courier[courier_id],
                key=lambda candidate: (
                    _group_assignment_cost([candidate]),
                    candidate.task_id_list,
                    candidate.index,
                ),
            )
            if candidates:
                courier_groups.append((courier_id, candidates))
        courier_groups.sort(
            key=lambda item: (
                _group_assignment_cost([item[1][0]]),
                item[0],
            )
        )

        task_count = len(instance.task_ids)
        empty_groups = tuple(() for _ in range(task_count))
        states = [(PENALTY_SCORE * task_count, empty_groups, 0)]

        for courier_id, candidates in courier_groups:
            if budget.expired():
                break
            next_states = []
            for state_score, task_groups, covered_mask in states:
                next_states.append((state_score, task_groups, covered_mask))
                for candidate in candidates:
                    task_index = task_index_by_id[candidate.task_ids[0]]
                    old_group = task_groups[task_index]
                    old_cost = (
                        _group_assignment_cost(list(old_group))
                        if old_group
                        else PENALTY_SCORE
                    )
                    new_group = old_group + (candidate,)
                    new_cost = _group_assignment_cost(list(new_group))
                    new_groups = list(task_groups)
                    new_groups[task_index] = new_group
                    new_mask = covered_mask | (1 << task_index)
                    next_states.append(
                        (
                            state_score - old_cost + new_cost,
                            tuple(new_groups),
                            new_mask,
                        )
                    )

            next_states.sort(key=lambda state: (state[0], -_popcount(state[2])))
            states = next_states[: self.beam_width]

        assignments = []
        for task_group in states[0][1]:
            for candidate in task_group:
                assignments.append(Assignment.from_candidate(candidate))
        candidate_solution = Solution(assignments=tuple(assignments))
        if is_better_solution(instance, candidate_solution, best):
            return candidate_solution
        return best


def _run_beam_variant(
    instance: ProblemInstance,
    budget: TimeBudget,
    candidates_by_courier,
    variant,
) -> Solution:
    beam_width, options_per_courier, rank_penalty, courier_order, option_order = variant
    beam_width = max(1, int(beam_width))
    options_per_courier = max(1, int(options_per_courier))

    courier_groups = []
    for courier_id in instance.courier_ids:
        options = sorted(
            candidates_by_courier[courier_id],
            key=lambda option: _beam_option_key(option, option_order),
        )[:options_per_courier]
        options.append((0.0, 0, None))
        best_cost = options[0][0] if options else 0.0
        best_saving = max(
            [
                PENALTY_SCORE * _popcount(option[1]) - option[0]
                for option in options
                if option[2] is not None
            ] or [0.0]
        )
        courier_groups.append((courier_id, options, best_cost, best_saving))

    if courier_order == "cost":
        courier_groups.sort(key=lambda item: (item[2], item[0]))
    elif courier_order == "save":
        courier_groups.sort(key=lambda item: (-item[3], item[0]))
    else:
        courier_groups.sort(key=lambda item: item[0])

    task_count = len(instance.task_ids)
    states = {0: (0.0, ())}
    best_assignments = ()

    for courier_id, options, _, _ in courier_groups:
        if budget.expired():
            break
        next_states = {}
        for used_task_mask, state in states.items():
            state_cost, state_candidates = state
            for option_cost, option_task_mask, option_candidate in options:
                if option_task_mask & used_task_mask:
                    continue
                next_task_mask = used_task_mask | option_task_mask
                next_cost = state_cost + option_cost
                previous = next_states.get(next_task_mask)
                if previous is not None and previous[0] <= next_cost:
                    continue
                if option_candidate is None:
                    next_candidates = state_candidates
                else:
                    next_candidates = state_candidates + (option_candidate,)
                next_states[next_task_mask] = (next_cost, next_candidates)

        if not next_states:
            break

        ordered_states = sorted(
            next_states.items(),
            key=lambda item: (
                _beam_state_score(item, task_count, rank_penalty),
                -_popcount(item[0]),
                item[1][0],
            ),
        )
        states = dict(ordered_states[:beam_width])
        best_assignments = ordered_states[0][1][1]

    return Solution(
        assignments=tuple(
            Assignment.from_candidate(candidate)
            for candidate in best_assignments
        )
    )


def _beam_option_key(option, option_order):
    cost, task_mask, candidate = option
    task_count = max(_popcount(task_mask), 1)
    if candidate is None:
        return (0, 0.0, 0.0, "", "", -1)
    if option_order == "saving":
        return (
            -(PENALTY_SCORE * task_count - cost),
            cost / task_count,
            cost,
            candidate.task_id_list,
            candidate.courier_id,
            candidate.index,
        )
    if option_order == "prob":
        return (
            -task_count,
            -candidate.willingness,
            cost / task_count,
            candidate.task_id_list,
            candidate.courier_id,
            candidate.index,
        )
    return (
        -task_count,
        cost / task_count,
        cost,
        candidate.task_id_list,
        candidate.courier_id,
        candidate.index,
    )


def _popcount(value: int) -> int:
    return bin(value).count("1")


def _beam_state_score(item, task_count: int, rank_penalty: float = PENALTY_SCORE) -> float:
    task_mask, state = item
    cost = state[0]
    return cost + (task_count - _popcount(task_mask)) * rank_penalty


def _build_task_pressures(instance: ProblemInstance):
    min_cost_by_task = {task_id: float("inf") for task_id in instance.task_ids}
    candidate_count_by_task = {task_id: 0 for task_id in instance.task_ids}

    for candidate in instance.candidates:
        unit_cost = candidate_assignment_cost(candidate) / len(candidate.task_ids)
        for task_id in candidate.task_ids:
            candidate_count_by_task[task_id] += 1
            if unit_cost < min_cost_by_task[task_id]:
                min_cost_by_task[task_id] = unit_cost

    max_min_cost = max(min_cost_by_task.values()) if min_cost_by_task else 1.0
    if max_min_cost <= 0.0:
        max_min_cost = 1.0
    max_inverse_count = max(
        1.0 / max(candidate_count_by_task[task_id], 1)
        for task_id in candidate_count_by_task
    ) if candidate_count_by_task else 1.0

    pressures = {}
    for task_id in instance.task_ids:
        inverse_count = 1.0 / max(candidate_count_by_task[task_id], 1)
        pressures[task_id] = (
            min_cost_by_task[task_id] / max_min_cost,
            inverse_count / max_inverse_count,
        )
    return pressures


def _run_pressure_variant(
    instance: ProblemInstance,
    budget: TimeBudget,
    pressures,
    candidate_costs,
    alpha: float,
    beta: float,
) -> Solution:
    used_couriers = set()
    task_package_by_task = {}
    assignments = []

    while not budget.expired():
        best_candidate = None
        best_key = None

        for candidate in instance.candidates:
            if candidate.courier_id in used_couriers:
                continue

            new_task_count = 0
            pressure_sum = 0.0
            conflicts = False
            for task_id in candidate.task_ids:
                existing_package = task_package_by_task.get(task_id)
                if existing_package is not None and existing_package != candidate.task_id_list:
                    conflicts = True
                    break
                if existing_package is None:
                    new_task_count += 1
                    min_cost_pressure, rarity_pressure = pressures[task_id]
                    pressure_sum += min_cost_pressure + beta * rarity_pressure

            if conflicts or new_task_count <= 0:
                continue

            cost = candidate_costs[candidate.index]
            key = (
                -new_task_count,
                cost / len(candidate.task_ids) - alpha * pressure_sum / new_task_count,
                cost,
                candidate.task_id_list,
                candidate.courier_id,
                candidate.index,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_candidate = candidate

        if best_candidate is None:
            break

        assignments.append(Assignment.from_candidate(best_candidate))
        used_couriers.add(best_candidate.courier_id)
        for task_id in best_candidate.task_ids:
            task_package_by_task[task_id] = best_candidate.task_id_list

    return Solution(assignments=tuple(assignments))


class ReinforceGreedy:
    name = "reinforce_greedy"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        if incumbent is None or not incumbent.assignments:
            return Solution.empty()

        assignments = list(incumbent.assignments)
        used_couriers = {courier_id for a in assignments for courier_id in a.courier_ids}

        candidates_by_courier = defaultdict(list)
        for candidate in instance.candidates:
            if candidate.courier_id not in used_couriers:
                candidates_by_courier[candidate.courier_id].append(candidate)

        task_groups = {}
        for a in assignments:
            task_groups.setdefault(a.candidate.task_id_list, []).append(a.candidate)

        improved = True
        while improved and not budget.expired():
            improved = False
            best_candidate = None
            best_saving = 0.0

            for cid, cands in candidates_by_courier.items():
                if cid in used_couriers:
                    continue
                for candidate in cands:
                    group = task_groups.get(candidate.task_id_list)
                    if group is None:
                        continue
                    old_cost = _group_assignment_cost(group)
                    new_cost = _group_assignment_cost(group + [candidate])
                    saving = old_cost - new_cost
                    if saving > best_saving:
                        best_saving = saving
                        best_candidate = candidate

            if best_candidate is not None and best_saving > 0:
                assignments.append(Assignment.from_candidate(best_candidate))
                used_couriers.add(best_candidate.courier_id)
                task_groups.setdefault(best_candidate.task_id_list, []).append(best_candidate)
                improved = True

        return Solution(assignments=tuple(assignments))


class SingletonMatchingGreedy:
    name = "singleton_matching_greedy"

    def run(
        self,
        instance: ProblemInstance,
        incumbent: Optional[Solution],
        budget: TimeBudget,
    ) -> Solution:
        base_solution = _build_singleton_matching_solution(instance, budget)
        if not base_solution.assignments or budget.expired():
            return base_solution
        return ReinforceGreedy().run(instance, base_solution, budget)


def _build_singleton_matching_solution(
    instance: ProblemInstance,
    budget: TimeBudget,
) -> Solution:
    singleton_candidates_by_task = {task_id: [] for task_id in instance.task_ids}
    for candidate in instance.candidates:
        if len(candidate.task_ids) == 1 and candidate.task_id_list == candidate.task_ids[0]:
            singleton_candidates_by_task[candidate.task_ids[0]].append(candidate)

    if not instance.task_ids or any(
        not singleton_candidates_by_task[task_id]
        for task_id in instance.task_ids
    ):
        return Solution.empty()

    task_count = len(instance.task_ids)
    courier_count = len(instance.courier_ids)
    source = 0
    task_offset = 1
    courier_offset = task_offset + task_count
    dummy_offset = courier_offset + courier_count
    sink = dummy_offset + task_count
    node_count = sink + 1
    graph = [[] for _ in range(node_count)]

    def add_edge(from_node, to_node, capacity, cost, candidate=None):
        graph[from_node].append(
            [to_node, capacity, cost, len(graph[to_node]), candidate]
        )
        graph[to_node].append(
            [from_node, 0, -cost, len(graph[from_node]) - 1, None]
        )

    for task_index in range(task_count):
        add_edge(source, task_offset + task_index, 1, 0.0)

    courier_index_by_id = {
        courier_id: courier_index
        for courier_index, courier_id in enumerate(instance.courier_ids)
    }
    for courier_index in range(courier_count):
        add_edge(courier_offset + courier_index, sink, 1, 0.0)

    for task_index, task_id in enumerate(instance.task_ids):
        best_candidate_by_courier = {}
        for candidate in singleton_candidates_by_task[task_id]:
            previous = best_candidate_by_courier.get(candidate.courier_id)
            if previous is None or candidate_assignment_cost(candidate) < candidate_assignment_cost(previous):
                best_candidate_by_courier[candidate.courier_id] = candidate

        task_node = task_offset + task_index
        for courier_id, candidate in best_candidate_by_courier.items():
            courier_node = courier_offset + courier_index_by_id[courier_id]
            add_edge(
                task_node,
                courier_node,
                1,
                candidate_assignment_cost(candidate),
                candidate,
            )

        dummy_node = dummy_offset + task_index
        add_edge(task_node, dummy_node, 1, PENALTY_SCORE)
        add_edge(dummy_node, sink, 1, 0.0)

    _send_min_cost_flow(graph, source, sink, task_count, budget)

    assignments = []
    for task_index in range(task_count):
        task_node = task_offset + task_index
        for edge in graph[task_node]:
            candidate = edge[4]
            if candidate is not None and edge[1] == 0:
                assignments.append(Assignment.from_candidate(candidate))

    return Solution(assignments=tuple(assignments))


def _send_min_cost_flow(graph, source, sink, required_flow, budget):
    node_count = len(graph)
    potentials = [0.0] * node_count
    flow = 0

    while flow < required_flow and not budget.expired():
        distances = [float("inf")] * node_count
        previous_node = [-1] * node_count
        previous_edge = [-1] * node_count
        distances[source] = 0.0
        queue = [(0.0, source)]

        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            for edge_index, edge in enumerate(graph[node]):
                if edge[1] <= 0:
                    continue
                next_node = edge[0]
                next_distance = distance + edge[2] + potentials[node] - potentials[next_node]
                if next_distance + 1e-12 < distances[next_node]:
                    distances[next_node] = next_distance
                    previous_node[next_node] = node
                    previous_edge[next_node] = edge_index
                    heapq.heappush(queue, (next_distance, next_node))

        if previous_node[sink] < 0:
            break

        for node in range(node_count):
            if distances[node] < float("inf"):
                potentials[node] += distances[node]

        node = sink
        while node != source:
            edge = graph[previous_node[node]][previous_edge[node]]
            edge[1] -= 1
            graph[node][edge[3]][1] += 1
            node = previous_node[node]

        flow += 1
