import json
from json import JSONDecodeError

from rich.pretty import pprint
from termcolor import cprint

def step_printer(steps):
    """
    Print the steps of an agent's response in a formatted way.
    Note: stream need to be set to False to use this function.
    Args:
    steps: List of steps from an agent's response.
    """
    for i, step in enumerate(steps):
        step_type = type(step).__name__
        print("\n"+"-" * 10, f"Step {i+1}: {step_type}","-" * 10)
        if step_type == "ToolExecutionStep":
            print("Executing tool...")
            try:
                pprint(json.loads(step.tool_responses[0].content))
            except Exception as e:
                print(f"Error displaying tool response: {e}")
        else:
            print(f"Step type: {step_type}")
            print(f"Step content: {step}")
    print("="*10, "Query processing completed","="*10,"\n")