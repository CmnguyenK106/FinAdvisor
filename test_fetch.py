import asyncio
from agent.core.config import load_config
from agent.core.graph import build_pre_draft_graph

async def main():
    cfg = load_config()
    graph, nodes = build_pre_draft_graph(cfg)
    graph = graph.compile()
    
    state = {
        "query": "VNM",
        "locale": "vi",
        "history": [],
    }
    
    print("Running graph...")
    result = graph.invoke(state)
    print("Data keys fetched:", result.get("data", {}).keys())
    print("Valuations:", result.get("valuations", []))
    print("Warnings:", result.get("warnings", []))
    print("Plan:", result.get("plan", {}))

if __name__ == "__main__":
    asyncio.run(main())
