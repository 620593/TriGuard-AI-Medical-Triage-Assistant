import time
from backend.src.nodes.red_flag_engine_node import _determine_urgency, red_flag_engine_node, _load_rules, _build_search_text

def generate_state():
    return {
        "symptoms": ["chest pain", "fever", "cough", "mild headache", "rash"] * 20,
        "user_input": "I have a lot of chest pain and a bad cough. " * 100,
        "reasoning_input": "Patient is experiencing chest pain and some fever. " * 100,
        "extracted_text": "Chest pain fever " * 100
    }

def benchmark():
    rules = _load_rules()
    state = generate_state()
    search_text = _build_search_text(state)

    iterations = 50000

    start_time = time.perf_counter()
    for _ in range(iterations):
        _determine_urgency(search_text, rules)
    end_time = time.perf_counter()

    print(f"Optimized Time for {iterations} _determine_urgency iterations: {end_time - start_time:.6f} seconds")

    start_time = time.perf_counter()
    for _ in range(iterations):
        state_copy = dict(state)
        red_flag_engine_node(state_copy)
    end_time = time.perf_counter()

    print(f"Optimized Time for {iterations} red_flag_engine_node iterations: {end_time - start_time:.6f} seconds")

if __name__ == "__main__":
    benchmark()