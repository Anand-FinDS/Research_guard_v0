from dotenv import load_dotenv
load_dotenv()
import os
from langsmith import Client, traceable

for k in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"):
    v = os.getenv(k)
    print(f"{k} = {'<set>' if k.endswith('KEY') and v else v}")

@traceable(name="langsmith_smoke_test")
def ping(x):
    return {"echo": x}

ping("hello")
c = Client()
c.flush()
print("projects:", [p.name for p in c.list_projects(limit=10)])