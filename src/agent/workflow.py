import dotenv
dotenv.load_dotenv()
import weave
from agents import Agent, Runner, SQLiteSession, ModelSettings
from openai.types.shared import Reasoning
from toolbox import compile_lean_code_tool, file_look_up_tool
from utils import (
    load_jsonl, 
    construct_query, 
    write_jsonl, 
    write_human_readable, 
    construct_data, 
    extract_code_block, 
    construct_agentic_query,
    construct_agentic_query_v2
)
from preprocessing.preprocess_dataset import preprocess_dataset
import asyncio
import os
from agents.exceptions import MaxTurnsExceeded
from globals import OUTPUT_DIR
from system_prompts import (
    SYSTEM_PROMPT_LC_JIXIA_AGENT, 
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V2,
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V2_1, 
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V3, 
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V3_1, 
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V4,
    SYSTEM_PROMPT_LC_JIXIA_AGENT_V4_1
)
weave.init("openai-agents")

MAX_CONCURRENT = 20
MODE = "jixia-agent"

Lean_Compiler_Agent = Agent(
    name="Lean Compiler Agent",
    model="gpt-5",
    instructions="You are a Lean compiler agent. You are responsible for writing Lean code that compiles. Please use the compile_lean_code_tool to test if the code compiles.",
    tools=[compile_lean_code_tool],
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high")
    )
)

Lean_Compiler_Jixia_Agent = Agent(
    name="Lean Compiler Jixia Agent",
    model="gpt-5",
    instructions=SYSTEM_PROMPT_LC_JIXIA_AGENT_V4_1,
    tools=[compile_lean_code_tool, file_look_up_tool],
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high")
    )
)


async def run_agent(query: str, session: SQLiteSession):
    result = await Runner.run(Lean_Compiler_Agent, input=query, session=session, max_turns=15)
    return result

async def run_agent_jixia(query: str, session: SQLiteSession):
    result = await Runner.run(Lean_Compiler_Jixia_Agent, input=query, session=session, max_turns=20)
    return result

async def process_query(query_idx, query_info, sem: asyncio.Semaphore):
    async with sem:
        local_session = SQLiteSession("lean_compiler_jixia_agent_" + str(query_idx) if MODE == "jixia-agent" else "lean_compiler_agent_" + str(query_idx))
        query = construct_agentic_query_v2(query_info) if MODE == "jixia-agent" else construct_query(query_info) 
     
        try:
            result = await run_agent_jixia(query, local_session) if MODE == "jixia-agent" else await run_agent(query, local_session)
            success = True
            error_info = None
            content = extract_code_block(result.final_output)
            last_agent = result.last_agent.name
            pretty = str(result)
        except MaxTurnsExceeded as e:
            # Agent spun too long; mark as failure but don't crash the job
            success = False
            error_info = {
                "type": "MaxTurnsExceeded",
                "message": str(e),
            }
            content = None
            last_agent = "Lean Compiler Agent"
            pretty = "MaxTurnsExceeded: agent hit turn limit without producing a final answer."
        except Exception as e:
            # Catch any other unexpected error similarly
            success = False
            error_info = {
                "type": type(e).__name__,
                "message": str(e),
            }
            content = None
            last_agent = "Lean Compiler Agent"
            pretty = f"Unhandled exception: {type(e).__name__}: {e}"

        return {
            "query_idx": query_idx,
            "chapter_name": query_info["chapter_name"],
            "FQN": query_info["FQN"],
            "original_theorem": query_info["content"],
            "content": content,
            "input": query,  # or result.input if success
            "last_agent": last_agent,
            "success": success,
            "error": error_info,
            "pretty": pretty,
        }

async def main():

    if MODE == "jixia-agent":
        data = load_jsonl("/Users/alextaylor/Desktop/lean_prover/src/output/gpt/processed_data_gpt.jsonl")
        unverified_theorems = load_jsonl("/Users/alextaylor/Desktop/lean_prover/output/union_unverified_theorems.jsonl")
        unverified_data_points = construct_data(data, unverified_theorems)
        unverified_data_FQNs = set([dp["FQN"] for dp in unverified_data_points])
        dataset = preprocess_dataset(force_reprocess=False)
        
        # unverified_data_FQNs = ["Chapter11.integ_zero", "Chapter9.StrictMonoOn.of_f_9_8_5", \
        #     "Chapter11.IntegrableOn.split", "Chapter3.SetTheory.Set.prod_inter", 
        #     "Chapter3.SetTheory.Set.prod_subset_prod", "Chapter11.RS_integ_of_uniform_cts"]
        # unverified_data_FQNs = ["Chapter5.Real.LIM_of_Cauchy"]
        # unverified_data_FQNs = ["Chapter3.SetTheory.Set.pair_exists", "Chapter3.SetTheory.Set.direct_sum", "Chapter3.SetTheory.Set.preimage_image_of_inj",\
        #     "Chapter3.SetTheory.Set.pigeonhole_principle", "Chapter5.Real.LIM_of_ge", "Chapter5.Real.LIM_of_Cauchy", "Chapter3.SetTheory.Set.diff_prod"]
        unverified_data_FQNs = ['Chapter3.SetTheory.Set.prod_diff', 'Chapter11.IntegrableOn.split', "Chapter11.DifferentiableOn.of_F_11_9_2'"]
        unverified_data = [dp for dp in dataset if dp["FQN"] in unverified_data_FQNs]
        print("Number of unverified data points: ", len(unverified_data))
    else:
        data = load_jsonl("/Users/alextaylor/Desktop/lean_prover/src/output/gpt/processed_data_gpt.jsonl")
        unverified_theorems = load_jsonl("/Users/alextaylor/Desktop/lean_prover/output/union_unverified_theorems.jsonl")
        unverified_data = construct_data(data, unverified_theorems)
        

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        process_query(query_idx, query_info, sem)
        for query_idx, query_info in enumerate(unverified_data)
    ]

    total = len(tasks)
    results_path = os.path.join(OUTPUT_DIR, "results_stream.jsonl")
    pretty_path = os.path.join(OUTPUT_DIR, "results_stream.txt")

    # truncate existing files
    open(results_path, "w").close()
    open(pretty_path, "w").close()
    results = []
    
    for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
        res = await coro
        results.append(res)
        print(f"[{i}/{total}] completed: {res['FQN']}")

        # append JSON line
        with open(results_path, "a") as f:
            import json
            f.write(json.dumps(res, ensure_ascii=False) + "\n")

        # append human-readable summary
        with open(pretty_path, "a") as f:
            f.write(f"=== #{i} {res['chapter_name']} :: {res['FQN']} ===\n")
            f.write(f"{res['content']}" + "\n\n")

    write_jsonl(OUTPUT_DIR, results)
    write_human_readable(OUTPUT_DIR, results)


if __name__ == "__main__":
    asyncio.run(main())