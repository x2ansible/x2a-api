#!/usr/bin/env python3
"""
Test script for Ansible Lint MCP tool via LlamaStack agent.
Cleans up and pretty-prints the lint result.
"""

from llama_stack_client import LlamaStackClient, Agent
import json

def get_lint_result_from_tool_response_content(content):
    """
    content: str, top-level JSON (with "text": inner-JSON-string)
    Returns: parsed dict of the real lint result, or None
    """
    try:
        top = json.loads(content)
        if isinstance(top, dict) and "text" in top:
            # This is the inner JSON string
            return json.loads(top["text"])
        return top
    except Exception as e:
        print("[WARN] Failed to parse tool_response content as JSON:", e)
        return None

def main():
    LLAMA_STACK_URL = "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com/"

    print("Testing Ansible Lint MCP Tool Calls")
    print("=" * 40)

    try:
        print("1. Connecting to Llama Stack...")
        client = LlamaStackClient(base_url=LLAMA_STACK_URL)
        print("   ✓ Connected")

        print("2. Creating agent...")
        agent = Agent(
            client,
            model="meta-llama/Llama-3.1-8B-Instruct",
            instructions="You are an Ansible expert. Use Ansible Lint tools when asked about linting.",
            tools=["mcp::ansible_lint"],
            tool_config={"tool_choice": "auto"},
            sampling_params={"strategy": {"type": "greedy"}, "max_tokens": 512}
        )
        print("   ✓ Agent created")

        print("3. Creating session...")
        session_id = agent.create_session("ansible_test")
        print("   ✓ Session created")

        playbook_content = """---
- name: Install and configure web server
  hosts: webservers
  tasks:
    - name: install nginx
      apt: 
        name: nginx
        state: present
    - name: start nginx
      service:
        name: nginx
        state: started
    - name: copy config file
      copy:
        src: nginx.conf
        dest: /etc/nginx/nginx.conf
      notify: restart nginx
    - name: ensure nginx is running
      service: name=nginx state=started enabled=yes
  handlers:
    - name: restart nginx
      service:
        name: nginx
        state: restarted"""

        query = "Use the lint_ansible_playbook tool with basic profile to check this playbook:\n\n" + playbook_content

        response = agent.create_turn(
            messages=[{
                "role": "user",
                "content": query
            }],
            session_id=session_id,
            stream=False
        )

        print("\n===== LINT RESULT =====\n")

        found_lint = False
        if hasattr(response, "steps"):
            for idx, step in enumerate(response.steps):
                # Only interested in tool_execution step with tool_responses
                if getattr(step, "step_type", "") == "tool_execution":
                    if hasattr(step, "tool_responses"):
                        for tool_response in step.tool_responses:
                            lint_json = get_lint_result_from_tool_response_content(getattr(tool_response, "content", ""))
                            if lint_json:
                                found_lint = True
                                summary = lint_json.get("output", {}).get("summary", {})
                                issues = lint_json.get("output", {}).get("issues", [])
                                raw_stdout = lint_json.get("output", {}).get("raw_output", {}).get("stdout", "")
                                raw_stderr = lint_json.get("output", {}).get("raw_output", {}).get("stderr", "")

                                print("Tool:", lint_json.get("tool"))
                                print("Success:", lint_json.get("success"))
                                print("Summary:", summary)
                                print()

                                if issues:
                                    print("Issues:")
                                    for issue in issues:
                                        print(" -", issue)
                                elif not summary.get("passed", False):
                                    print("No structured issues, but playbook did NOT pass.")
                                else:
                                    print("No issues found. Playbook passed lint!")

                                print("\nRaw Output (stdout):\n", raw_stdout)
                                print("\nRaw Output (stderr):\n", raw_stderr)
        if not found_lint:
            print("No lint result found in tool responses.")

        print("\n===== END =====\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print("\nTroubleshooting:")
        print("- Check if Llama Stack server is running")
        print("- Verify the server URL is correct")
        print("- Ensure MCP endpoint is accessible")

if __name__ == "__main__":
    main()
