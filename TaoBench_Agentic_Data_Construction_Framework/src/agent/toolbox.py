from toolchest.compile_lean_code import compile_lean_code
from toolchest.file_look_up import file_look_up
from agents import function_tool

@function_tool
def compile_lean_code_tool(code: str) -> str:
    return compile_lean_code(code)

@function_tool
def file_look_up_tool(chapter_name: str) -> str:
    return file_look_up(chapter_name)