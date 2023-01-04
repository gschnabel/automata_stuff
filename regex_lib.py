from automaton_stuff import Automaton, DFA, NFA
from automaton_stuff.algos import (
    create_DFA_from_rex,
    create_NFA_from_rex,
    convert_NFA_to_NFA_without_eps
)
from automaton_stuff.utils.regex_utils import expand_plus, locate_union_symb
from automaton_stuff.utils.visualization import plot_automaton

# create an automaton manually
auto = Automaton()
auto.create_state(0)
auto.create_state(1)
auto.create_state(2)
auto.create_state(3)
auto.add_transition(0, 3, 'a')
auto.add_transition(1, 3, 'b')
auto.add_transition(0, 1, 'c')
auto.add_transition(0, 2, 'y')

print('States in automaton: ')
print(auto.list_states())

print('Transitions in automaton: ')
print(auto.list_transitions())

plot_automaton(auto)

auto.remove_state(0)
auto.remove_transition(1, 3, 'b')


# basic checking of NFA-delta to DFA
auto = create_NFA_from_rex(r'(a\+b|ab|a+)+')
auto = convert_NFA_to_NFA_without_eps(auto)


auto = create_DFA_from_rex(r'(a\+b|ab|a+)+')
plot_automaton(auto)

auto.is_valid_input('a+caaaaab')
