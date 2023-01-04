from ..automaton import Automaton
from ..DFA import DFA
from ..utils.regex_utils import (
    locate_union_symb,
    remove_caret_and_dollar
)


def _duplicate_automaton_part(
        automaton, start_state, clone_state=None, state_map=None
):
    state_map = state_map if state_map is not None else dict()
    clone_state = automaton.create_state() if clone_state is None else clone_state
    state_map[start_state] = clone_state
    terminal_states = list()
    out_transitions = automaton.list_transitions(source_states=(start_state,))
    for _, outstate, inpsym in out_transitions:
        if outstate in state_map:
            new_state = state_map[outstate]
        else:
            new_state = automaton.create_state()
        automaton.add_transition(clone_state, new_state, inpsym)
        if outstate not in state_map:
            _, new_terminal_states, _ = _duplicate_automaton_part(
                automaton, outstate, new_state, state_map
            )
            terminal_states.append(new_terminal_states)
    if len(automaton.outgoing[start_state]) == 0:
        terminal_states = set((clone_state,))
    else:
        terminal_states = set((x for y in terminal_states for x in y))
    return clone_state, terminal_states, state_map


def _create_NFA_from_rex(automaton, rex, pos=0, cur_state=None):
    is_most_outer_call = cur_state is None
    cur_state = automaton.create_state(cur_state)
    if is_most_outer_call:
        automaton.set_initial_state(cur_state)
    while pos < len(rex) and rex[pos] != ')':
        cursymb = rex[pos]
        union_pos = locate_union_symb(rex, pos)
        if union_pos is not None:
            left_temp_state = automaton.create_state()
            right_temp_state = automaton.create_state()
            automaton.add_transition(cur_state, left_temp_state, 'eps')
            automaton.add_transition(cur_state, right_temp_state, 'eps')
            left_pos, left_terminal_state = _create_NFA_from_rex(
                automaton, rex[:union_pos], pos, left_temp_state
            )
            right_pos, right_terminal_state = _create_NFA_from_rex(
                automaton, rex, union_pos+1, right_temp_state
            )
            terminal_state = automaton.create_state()
            automaton.add_transition(left_terminal_state, terminal_state, 'eps')
            automaton.add_transition(right_terminal_state, terminal_state, 'eps')
            pos = right_pos
            if rex[pos] == ')':
                pos -= 1
        # treat brackets
        elif cursymb == '(':
            temp_state = automaton.create_state()
            automaton.add_transition(cur_state, temp_state, 'eps')
            pos, terminal_state = _create_NFA_from_rex(
                automaton, rex, pos+1, temp_state
            )
            if len(rex) == pos or rex[pos] != ')':
                raise IndexError('missing closing bracket')
        # treat regular symbol
        else:
            if cursymb == '\\':
                pos += 1
                cursymb = rex[pos]
            terminal_state = automaton.create_state()
            automaton.add_transition(cur_state, terminal_state, cursymb)
        # treat with ?,+,*
        rex_symb = rex[pos+1] if pos+1 < len(rex) else ''
        # perform an automaton duplication for `+`
        if rex_symb == '+':
            clone_state, new_terminal_states, _ = \
                _duplicate_automaton_part(automaton, cur_state)
            automaton.add_transition(terminal_state, clone_state, 'eps')
            cur_state = clone_state
            if len(new_terminal_states) != 1:
                raise IndexError('expect exactly one terminal state here')
            terminal_state = new_terminal_states.pop()
        # create appropriate epsilon transitions
        if rex_symb in ('?', '+', '*'):
            automaton.add_transition(cur_state, terminal_state, 'eps')
            if rex_symb in ('+', '*'):
                automaton.add_transition(terminal_state, cur_state, 'eps')
            pos += 1
        pos += 1
        cur_state = terminal_state
        if is_most_outer_call:
            automaton.set_terminal_states(set((cur_state,)))
    return pos, cur_state


def create_NFA_from_rex(rex):
    rex = remove_caret_and_dollar(rex)
    auto = Automaton()
    _create_NFA_from_rex(auto, rex)
    return auto


def _determine_transitions(auto, state, visited=None):
    if visited is None:
        visited = set()
    elif state in visited:
        return (set(), False)
    visited.add(state)
    all_transitions = auto.list_transitions(source_states=(state,))
    eps_transitions = set((t for t in all_transitions if t[2] == 'eps'))
    new_transitions = set((t for t in all_transitions if t[2] != 'eps'))
    terminal_state_flag = auto.is_terminal_state(state)
    for transition in eps_transitions:
        outstate = transition[1]
        inherited_transitions, inherited_terminal_state_flag = \
            _determine_transitions(auto, outstate, visited)
        new_transitions.update(inherited_transitions)
        if inherited_terminal_state_flag:
            terminal_state_flag = True
    return new_transitions, terminal_state_flag


def convert_NFA_to_NFA_without_eps(original_automaton):
    auto = original_automaton
    clone_auto = Automaton()
    state_map = dict()
    # create new states for each nfa state
    states = auto.list_states()
    for s in states:
        new_state = clone_auto.create_state()
        state_map[s] = new_state
    # set initial state of new nfa
    original_initial_state = auto.get_initial_state()
    new_initial_state = state_map[original_initial_state]
    clone_auto.set_initial_state(new_initial_state)
    # add transitions
    for state in states:
        curtransitions, is_terminal_state = _determine_transitions(auto, state)
        new_source_state = state_map[state]
        if is_terminal_state:
            clone_auto.add_terminal_state(new_source_state)
        for _, target_state, sym in curtransitions:
            new_target_state = state_map[target_state]
            clone_auto.add_transition(new_source_state, new_target_state, sym)
    # remove unreachable states
    unreachable = clone_auto.determine_unreachable_states()
    for s in unreachable:
        clone_auto.remove_state(s)
    return clone_auto


def convert_NFA_without_eps_to_DFA(original_automaton):
    auto = original_automaton
    new_auto = Automaton()
    initial_state = auto.get_initial_state()
    new_initial_state = new_auto.create_state()
    new_auto.set_initial_state(new_initial_state)
    state_sets = dict()
    state_sets[new_initial_state] = set((initial_state,))
    visited = dict()
    untreated_states = set((new_initial_state,))
    while len(untreated_states) > 0:
        curstate = untreated_states.pop()
        orig_source_states = state_sets[curstate]
        visited[tuple(sorted(orig_source_states))] = curstate
        transitions = auto.list_transitions(source_states=orig_source_states)
        sym_dict = dict()
        for t in transitions:
            cursym = t[2]
            curtransitions = sym_dict.setdefault(cursym, set())
            curtransitions.add(t)
        for sym, ts in sym_dict.items():
            new_state_set = set(t[1] for t in ts)
            new_state_tuple = tuple(sorted(new_state_set))
            if new_state_tuple in visited:
                target_state = visited[new_state_tuple]
                new_auto.add_transition(curstate, target_state, sym)
            else:
                new_state = new_auto.create_state()
                untreated_states.add(new_state)
                is_terminal_state = any(
                    (auto.is_terminal_state(tt[1]) for tt in ts)
                )
                if is_terminal_state:
                    new_auto.add_terminal_state(new_state)
                state_sets[new_state] = new_state_set
                new_auto.add_transition(curstate, new_state, sym)
    return DFA(new_auto)


def convert_DFA_to_minimal_DFA(original_automaton):
    auto = original_automaton
    if not isinstance(auto, DFA):
        raise TypeError(
            'a DFA (deterministic finite automaton) is expected as input'
        )
    all_states = auto.list_states()
    terminal_states = auto.get_terminal_states()
    nonterminal_states = all_states.difference(terminal_states)
    # determine partitions corresponding to states of minimal DFA
    partitions = list((terminal_states, nonterminal_states))
    state_partition_map = dict()
    state_partition_map.update({s: 0 for s in terminal_states})
    state_partition_map.update({s: 1 for s in nonterminal_states})
    is_terminal_partition = [True, False]
    while True:
        partitions_changed = False
        for i, curpartition in enumerate(tuple(partitions)):
            untreated = curpartition.copy()
            new_partition = curpartition
            is_curpart_terminal = is_terminal_partition[i]
            while True:
                curstate = untreated.pop()
                curts = auto.list_transitions(source_states=(curstate,))
                curts = set((t[2], state_partition_map[t[1]]) for t in curts)
                disting = set()
                while len(untreated) > 0:
                    teststate = untreated.pop()
                    testts = auto.list_transitions(source_states=(teststate,))
                    testts = set((t[2], state_partition_map[t[1]]) for t in testts)
                    if curts != testts:
                        disting.add(teststate)
                if len(disting) == 0:
                    break
                partitions_changed = True
                new_partition.difference_update(disting)
                new_partition = disting
                partitions.append(new_partition)
                is_terminal_partition.append(is_curpart_terminal)
                untreated = new_partition.copy()
        # update the state_partition_map
        for i, p in enumerate(partitions):
            for s in p:
                state_partition_map[s] = i
        if not partitions_changed:
            break
    # construct the minimal DFA
    new_auto = Automaton()
    for i in range(len(partitions)):
        new_auto.create_state(i)
        if is_terminal_partition[i]:
            new_auto.add_terminal_state(i)
    for i, p in enumerate(partitions):
        orig_source_state = p.pop()
        p.add(orig_source_state)
        trans = auto.list_transitions(source_states=(orig_source_state,))
        trans = set((i, state_partition_map[t[1]], t[2]) for t in trans)
        for t in trans:
            new_auto.add_transition(t[0], t[1], t[2])
    orig_initial_state = auto.get_initial_state()
    new_auto.set_initial_state(state_partition_map[orig_initial_state])
    return DFA(new_auto)


def convert_NFA_to_DFA(automaton):
    auto = convert_NFA_to_NFA_without_eps(automaton)
    auto = convert_NFA_without_eps_to_DFA(auto)
    auto = convert_DFA_to_minimal_DFA(auto)
    return auto


def create_DFA_from_rex(rex):
    auto = create_NFA_from_rex(rex)
    auto = convert_NFA_to_DFA(auto)
    return auto