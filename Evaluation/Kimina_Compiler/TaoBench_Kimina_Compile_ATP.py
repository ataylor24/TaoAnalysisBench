
def extract_lean_block(text: str) -> str:
    """Pull the last ```lean4 ... ``` block or best-effort fallback."""
    if "```lean4" in text:
        tail = text.split("```lean4")[-1]
        return tail.rsplit("```", 1)[0].strip()   # Find the last "```" and split backward from there.
    return text.strip()



import re
import textwrap
from pathlib import Path

def extract_proof_body(model_output: str) -> str:

    m = re.search(r":=\s*by[ \t]*\n", model_output)
    if not m:
        m = re.search(r":=\s*by\b[ \t]*", model_output)
        if not m:
            return ""

    body = model_output[m.end():].replace("```", "")
    print(body)
    
    if not body.strip():
        return ""
    
    return body



def replace_last_sorry(original_lean: str, proof_body: str) -> str:

    print(original_lean)

    matches = list(re.finditer(r"(?m)^(\s*)sorry\s*$", original_lean))
    if not matches:
        raise ValueError("couldn't find a standalone `sorry` in the original file.")

    last = matches[-1]
    indent = last.group(1)

    print(original_lean[last.end():].strip())

    return original_lean[:last.start()].strip() + "\n" + proof_body + "\n"



# ---------------------------------------------------------------------------------



def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _msg_field(m, key, default=None):
    if isinstance(m, dict):
        return m.get(key, default)
    return getattr(m, key, default)


# No error AND no sorry -> accepted as "proved"
def can_run_strict(repl_resp) -> bool:
    resp = _get(repl_resp, "response")
    if resp is None:
        return False

    messages = _get(resp, "messages", []) or []
    sorries = _get(resp, "sorries", []) or []

    # 1) Any error counts as a failure.
    if any((_msg_field(m, "severity") == "error") for m in messages):
        return False


    # ---------------------------------------------------------------------
    # In the Tao version, since sorry has already been removed from the proof, sorry in the context is allowed.

    """
    # 2) As long as there are any sorries (the REPL will list them), it counts as a failure.
    if len(sorries) > 0:
        return False
    """

    # ---------------------------------------------------------------------


    return True


# ---------------------------------------------------------------------------------




import json

file_path = "./Tao_Version_ModelEval_DeepSeekV2_7B_noCOT.jsonl"


with open(file_path, "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f]

print(len(data)) 



from kimina_client import KiminaClient
from kimina_client.models import Snippet


num_Pass = 0
Pass_Data = []
Fail_Data = []

client = KiminaClient(api_url="http://127.0.0.1:8000")




import os
from tqdm import tqdm
import re

answers_file = "./Tao_Version_ModelEval_DeepSeekV2_7B_noCOT_Compile.jsonl"

os.makedirs(os.path.dirname(answers_file), exist_ok=True)
ans_file = open(answers_file, "w")



for i in range(len(data)):

    print("#########################################")
    print(i)
    print(data[i]["idx"])
    prompt = data[i]["prompt"]
    lean_exercise = extract_lean_block(prompt)
    print(lean_exercise)


    if_Pass = 0
    final_exercise_result_All = []
    for k in range(len(data[i]["proofs"])):

        cleaned_proof = data[i]["proofs"][k]["cleaned_proof"]
        # print(cleaned_proof)
        
        cleaned_proof_body = extract_proof_body(cleaned_proof)
        # print(cleaned_proof_body)


        # --------------------------------------------------------------------------------
        # Replace "sorry" in proof body
        
        cleaned_proof_body = cleaned_proof_body.replace("sorry", "ERROR")

        cleaned_proof_body = cleaned_proof_body.replace("admit", "ERROR")

        # --------------------------------------------------------------------------------


        print("-------------------------------------------")
        final_exercise_result = replace_last_sorry(lean_exercise, cleaned_proof_body)
        print(final_exercise_result)


        final_exercise_result_All.append(final_exercise_result)

    print(len(final_exercise_result_All))


    snippets = [Snippet(id=str(i), code=final_exercise_result_All[i]) for i in range(len(final_exercise_result_All))]
    # resp = client.check(snippets, timeout=120, batch_size=5)
    resp = client.check(snippets, timeout=120, batch_size=1)
    

    # --------------------------------------------------------------------------------------
    
    if_Pass = 0
    # print(len(resp.results))

    Pass_Idx = []
    for r in resp.results:
        print("###############################################")
        print(r)
        # if_run = can_run(r)
        if_run = can_run_strict(r)
        print(if_run)

        if if_run == True:
            rid = _get(r, "id", None)
            if_Pass = 1
            print(i)
            print(rid)
            Pass_Idx.append(rid)


    if if_Pass == 1:
        print("Pass!")
        num_Pass += 1

        Now_Result = {"idx": data[i]["idx"], "Compilation": "Pass", "Pass_Idx": Pass_Idx}
        ans_file.write(json.dumps(Now_Result) + "\n")
        ans_file.flush()

    else:
        print("Fail!")

        Now_Result = {"idx": data[i]["idx"], "Compilation": "Fail", "Pass_Idx": Pass_Idx}
        ans_file.write(json.dumps(Now_Result) + "\n")
        ans_file.flush()

    print(num_Pass)
    # --------------------------------------------------------------------------------------


ans_file.close()

print(num_Pass)
