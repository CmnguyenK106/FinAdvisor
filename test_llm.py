import os
from agent.core.config import load_config
from agent.core.llm import build_llm

def main():
    cfg = load_config()
    print("Model:", cfg.openrouter_model)
    try:
        llm = build_llm(cfg)
        print("Invoking model...")
        response = llm.invoke("hello")
        print("Response:", response.content)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()
