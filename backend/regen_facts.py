# regen_facts.py
from chat_cf_rag import generate_facts
from facts_store import save_facts

facts = generate_facts(n=30)
save_facts(facts)
print(f"Generated {len(facts)} facts and saved them to facts.json")
