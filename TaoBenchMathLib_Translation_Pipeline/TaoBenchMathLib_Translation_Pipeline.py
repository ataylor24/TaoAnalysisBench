
import json

file_path = "/your_path/tao_analysis_exercises.jsonl"

with open(file_path, "r", encoding="utf-8") as f:
    data = [json.loads(line) for line in f]

print(len(data))

print(data[0].keys())



################################################################################################################################



from openai import OpenAI
import os
import json

client = OpenAI(api_key="your_api_key")



################################################################################################################################



Instruction = """The above is a Lean formalization exercise of a problem from Terence Tao's Analysis I. Many of the concepts in the given Lean code use local definition / local notation.
Please complete the following tasks:
1. First, understand and analyze the problem: read the given Lean code and the problem statement, and explain what the problem means mathematically.
2. Then, restate the problem using only standard definitions from Mathlib (no need to provide a proof). That is, rewrite the original problem, which uses local definitions / local notation, into a version that uses only the existing standard definitions in Mathlib. Only keep the formal statement of the problem (i.e. the Lean theorem / proposition statement), and do not give any proof.

In the Lean code, you may only use the following imports and settings:

import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat Set Filter

Do not add any other imports, and do not introduce any new local definitions or notation.
Please first give your analysis, and then provide the rewritten Lean problem statement (theorem declaration) using only the above restrictions, without any proof.

The theorem must keep the same name and end with := by sorry. You must ensure that this Lean code can be compiled in Lean4 and that the mathematical problem it describes is consistent with Terence Tao's exercise I gave you.

At the very end of your response, include your final Mathlib version of the problem in the following format (replace {Mathlib Version of the Problem} with your theorem declaration).

### Mathlib Version:
```lean4
import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat Set Filter

namespace New_Namespace

{Mathlib Version of the Problem}

end New_Namespace
```"""


################################################################################################################################



Instruction_ErrorCorrection_1 = """The above is a Lean formalization exercise of a problem from Terence Tao's Analysis I. Many of the concepts in the given Lean code use local definition / local notation.
Please complete the following tasks:
1. First, understand and analyze the problem: read the given Lean code and the problem statement, and explain what the problem means mathematically.
2. Then, restate the problem using only standard definitions from Mathlib (no need to provide a proof). That is, rewrite the original problem, which uses local definitions / local notation, into a version that uses only the existing standard definitions in Mathlib. Only keep the formal statement of the problem (i.e. the Lean theorem / proposition statement), and do not give any proof.

In the Lean code, you may only use the following imports and settings:

import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat Set Filter

Do not add any other imports, and do not introduce any new local definitions or notation.
Please first give your analysis, and then provide the rewritten Lean problem statement (theorem declaration) using only the above restrictions, without any proof.

The theorem must keep the same name and end with := by sorry. You must ensure that this Lean code can be compiled in Lean4 and that the mathematical problem it describes is consistent with Terence Tao's exercise I gave you."""



Instruction_ErrorCorrection_2 = """At the very end of your response, include your final Mathlib version of the problem in the following format (replace {Mathlib Version of the Problem} with your theorem declaration).

### Mathlib Version:
```lean4
import Mathlib
import Aesop
set_option maxHeartbeats 0
open BigOperators Real Nat Topology Rat Set Filter

namespace New_Namespace

{Mathlib Version of the Problem}

end New_Namespace
```"""



################################################################################################################################



# Compiler

import pathlib
import subprocess

PROJECT_ROOT = pathlib.Path("/your_path/LEAN_Project")

def check_lean_snippet(snippet: str):
    tmp_path = PROJECT_ROOT / "Test.lean"   
    tmp_path.write_text(snippet, encoding="utf-8")

    proc = subprocess.run(
        ["lake", "env", "lean", str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=PROJECT_ROOT,         
    )

    ok = proc.returncode == 0
    output = proc.stdout + "\n" + proc.stderr
    return ok, output




################################################################################################################################



# Replace Last ":= by\nsorry"

import re


def replace_last_by_sorry(text: str) -> str:

    pattern = re.compile(r":= by\s+sorry\b")

    matches = list(pattern.finditer(text))
    if not matches:
        return text

    last = matches[-1]    
    start, end = last.start(), last.end()

    replacement = ":= by\n  sorry"
    new_text = text[:start] + replacement + text[end:]
    return new_text




################################################################################################################################



import json

def read_state(file_name: str):

    with open(file_name, "r", encoding="utf-8") as f:
        data = json.load(f)

    All_State = []

    for entry in data:
        states = entry.get("state", [])
        if not states:
            continue 

        for st in states:
            now_State = ""

            ctx = st.get("context", [])
            goal = st.get("type", "")

            for hyp in ctx:
                name_list = hyp.get("name", [])
                if name_list:
                    name = str(name_list[-1])  
                else:
                    name = "_"

                ty = hyp.get("type", "")
                now_State += f"{name} : {ty}\n"
                # print(f"{name} : {ty}")

            now_State += f"⊢ {goal}"
            All_State.append(now_State)
            # print(f"⊢ {goal}")
            # print("---------------------------------------------")
    
    print("##############################################")
    print(len(All_State))
    for m in range(len(All_State)):
        print("--------------")
        print(All_State[m])
    print("##############")
    print(All_State[-1])

    Final_State = All_State[-1]

    return Final_State



################################################################################################################################



import subprocess
from pathlib import Path

def Get_State_Jixia(exercise: str):

  lean_file = Path("./Jixia_Test.lean")
  lean_file.write_text(exercise, encoding="utf-8")
  
  output_file = "Jixia_Test.lines.json"

  cmd = [
      "lake", "env",
      "/data2/junyizhang/RAG4FormalMathProving/jixia/.lake/build/bin/jixia",
      "-i",
      "-l", output_file,
      str(lean_file),
  ]

  print("Running command:")
  print(" ".join(cmd))

  result = subprocess.run(
      cmd,
      text=True,
      capture_output=True,
      check=False, 
  )

  if result.returncode != 0:
    raise ValueError("Jixia Error!")
  

  Final_State = read_state(output_file)

  return Final_State



################################################################################################################################


Instruction_Check_1 = """You are an expert in Lean4 and mathlib, and you are familiar with how the same mathematical statement can be represented in different formalizations, with different inductive definitions, notations, or contexts.

I will give you two versions of what is supposed to be the same exercise from Terence Tao's *Analysis I*:

1. Terence Tao exercise (Lean4 code)
2. Terence Tao goal state (the final statement to be proved)
3. Mathlib version exercise (Lean4 code)
4. Mathlib version goal state (the final statement to be proved)

Your task is to decide whether these two versions are proving the same mathematical statement."""


Instruction_Check_2 = """Please proceed in the following steps:
1. First, understand and analyze the two versions separately: read the given Lean code of each exercise and its corresponding goal state to be proved, and explain what the exercise means mathematically.
2. Then, compare the two versions. Check whether the assumptions match logically (allowing for renaming of variables and standard equivalences), check whether the conclusions match logically, and then decide whether they are the same mathematical statement or if there is a real difference.

At the very end of your response, give your final answer of "Yes" or "No" in the following format (replace `{Your final decision}` with "Yes" if they are mathematically equivalent, or "No" if they are not mathematically equivalent).

### Mathematical equivalence:
{Your final decision}"""




################################################################################################################################


import os
from tqdm import tqdm
import re


answers_file = "./GPT_Convert_Pipeline_Result_countRound.jsonl"
os.makedirs(os.path.dirname(answers_file), exist_ok=True)
ans_file = open(answers_file, "w")


for i in tqdm(range(len(data) - 1, -1, -1)):

    The_Final_Converted_Mathlib_Version = "None"
    
    print("#####################################################################################################")
    print("#####################################################################################################")
    print("#####################################################################################################")
    print(f"### Exercise {i}")

    num_iter = 0

    num_MathEqual_iter = 0

    num_LeanError_iter = []


    while(1):
        num_iter += 1
        print("#####################################################################################################")
        print("#####################################################################################################")
        print(f"### num_iter {num_iter}")

        index = data[i]["index"]
        chapter_name = data[i]["chapter_name"]
        FQN = data[i]["FQN"]
        
        Tao_Ver_exercise = data[i]["content"].strip()


        prompt = f"```lean4\n{Tao_Ver_exercise}\n```" + "\n\n\n" + Instruction

        print("###########################################")
        print(i)
        print(prompt)

        response = client.responses.create(
            model="gpt-5.1",
            input=prompt,
            tools=[
                {"type": "web_search"}
            ],
            tool_choice="required",
            reasoning={
                "effort": "high"
            }
        )

        response_dict = response.model_dump()
        # print(response_dict)

        # ------------------------------------------------------------------------------
        print("----------------------------------------------------")

        output_text = response_dict["output"][-1]["content"][0]["text"]

        pattern = r"### Mathlib Version:\s*```lean4\s*(.*?)```"
        match = re.search(pattern, output_text, re.DOTALL)

        if match:
            Mathlib_Ver_exercise = match.group(1).strip()
            print(Mathlib_Ver_exercise)
        else:
            continue
            # raise ValueError("Error!")


        # ------------------------------------------------------------------------------
        print("----------------------------------------------------")

        ok, out = check_lean_snippet(Mathlib_Ver_exercise)
        out = out.strip()
        print(ok)
        print("-----")
        print(out)


        # ------------------------------------------------------------------------------
        print("----------------------------------------------------")

        num_correction = 0

        if ok == False:
            print("!!!!!!!!!!!!!!!!!!!!!! Correction Process !!!!!!!!!!!!!!!!!!!!!!")
            latest_Answer = Mathlib_Ver_exercise.strip()
            error_Message = out.strip()

            # times limit
            # num_correction = 0

            while(1):
                num_correction += 1
                print(f"### The {num_correction} pass ###")

                prompt_correction = f"```lean4\n{Tao_Ver_exercise}\n```" + "\n\n\n" + Instruction_ErrorCorrection_1 + f"\n\n\n### This is your latest version of the answer:\n```lean4\n{latest_Answer}\n```\n\n### However, it has compilation errors. The error message is:\n{error_Message}\n\n### Please fix the errors while maintaining the mathematical meaning.\n\n\n" + Instruction_ErrorCorrection_2

                print(prompt_correction)

                response = client.responses.create(
                    model="gpt-5.1",
                    input=prompt_correction,
                    tools=[
                        {"type": "web_search"}
                    ],
                    tool_choice="required",
                    reasoning={
                        "effort": "high"
                    }
                )

                response_dict = response.model_dump()
                # print(response_dict)


                # ------------------------------------------------------------------------------
                print("----------------------------------------------------")

                output_text = response_dict["output"][-1]["content"][0]["text"]

                pattern = r"### Mathlib Version:\s*```lean4\s*(.*?)```"
                match = re.search(pattern, output_text, re.DOTALL)

                if match:
                    Mathlib_Ver_exercise = match.group(1).strip()
                    print(Mathlib_Ver_exercise)
                else:
                    continue
                    # raise ValueError("Error!")


                # ------------------------------------------------------------------------------
                print("----------------------------------------------------")

                ok, out = check_lean_snippet(Mathlib_Ver_exercise)
                out = out.strip()
                print(ok)
                print("Lean output:")
                print(out)

                if ok == True:
                    break
                else:
                    latest_Answer = Mathlib_Ver_exercise.strip()
                    error_Message = out.strip()


            print("!!!!!!!!!!!!!!!!!!!!!! Correction Process Finished !!!!!!!!!!!!!!!!!!!!!!")

            print(Mathlib_Ver_exercise)
            print("-----")
            print(ok)
            print("-----")
            print(out)

            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        num_LeanError_iter.append(num_correction)


        ######################################################################################################
        ### Check Pipeline:

        Final_Mathlib_Ver_exercise = Mathlib_Ver_exercise
        Final_Tao_Ver_exercise = Tao_Ver_exercise

        Final_Mathlib_Ver_exercise = replace_last_by_sorry(Final_Mathlib_Ver_exercise)
        Final_Tao_Ver_exercise = replace_last_by_sorry(Final_Tao_Ver_exercise)


        State_Mathlib_Ver_exercise = Get_State_Jixia(Final_Mathlib_Ver_exercise)
        State_Tao_Ver_exercise = Get_State_Jixia(Final_Tao_Ver_exercise)


        print("!!!!!!!!!!!!!!!!!!!!!! Final State !!!!!!!!!!!!!!!!!!!!!!")
        print(State_Mathlib_Ver_exercise)
        print("-----")
        print(State_Tao_Ver_exercise)
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")


        prompt_check = Instruction_Check_1 + f"\n\n### Terence Tao exercise:\n```lean4\n{Final_Tao_Ver_exercise}\n```\n\n### Terence Tao goal state:\n{State_Tao_Ver_exercise}\n\n\n### Mathlib version exercise:\n```lean4\n{Final_Mathlib_Ver_exercise}\n```\n\n### Mathlib version goal state:\n{State_Mathlib_Ver_exercise}\n\n\n" + Instruction_Check_2

        print(prompt_check)

        response = client.responses.create(
            model="gpt-5.1",
            input=prompt_check,
            tools=[
                {"type": "web_search"}
            ],
            tool_choice="required",
            reasoning={
                "effort": "high"
            }
        )

        response_dict = response.model_dump()


        # ------------------------------------------------------------------------------
        print("----------------------------------------------------")

        output_text = response_dict["output"][-1]["content"][0]["text"].strip()

        print(output_text)

        pattern = r"^### Mathematical equivalence:\s*([^\r\n]+)"
        match = re.search(pattern, output_text, re.MULTILINE)

        if match:
            answer_Equal = match.group(1).strip()
            answer_Equal = answer_Equal.lower()
            print(answer_Equal)
        else:
            answer_Equal = "None"
            # raise ValueError("Error!")



        if answer_Equal == "yes":
            The_Final_Converted_Mathlib_Version = Final_Mathlib_Ver_exercise
            break
        
        else:
            num_MathEqual_iter += 1

    
    # ------------------------------------------------------------------------------

    print("#####################################################################################################")
    print(f"### Save Exercise {i}")
    print(The_Final_Converted_Mathlib_Version)

    Answer = {"index": data[i]["index"], "chapter_name": data[i]["chapter_name"], "FQN": data[i]["FQN"], "num_iter": num_iter, "num_MathEqual_iter": num_MathEqual_iter, "num_LeanError_iter": num_LeanError_iter, "Mathlib_Version": The_Final_Converted_Mathlib_Version, "Tao_Version": data[i]["content"]}

    ans_file.write(json.dumps(Answer) + "\n")

    ans_file.flush()

ans_file.close()
