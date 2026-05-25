# Constraints and facts

## facts to remember:

- i develope and run this in an offline enterprise environment
- i have access to pip and npm via artifactory as aproxy to those repos
- i have access to gemini 2.5 pro model via local api wrapper that serves open-ai-compatible api
- i will use git only for versioning and storing, the agents will perform everything only on the local disk of my dev workstation
- i will use ADK as my multi-agent system
- the source code is a java IBM composer monolith and the destination code should be the user's choice between nodejs to java, and pack them as microservices.
- all the code should be documented inline and with a md files doc folder
- test and validation are crucial to this peocess to run test on the old version and compare it to the current new generated version (it will need to crate stubs and emulated requests probably based on old log files from the current runnable composer system.)
- the structure of themulti-agent system folders should be something like this (to avoid huge monolith abd avoid massive code duplication):

```
my_adk_project/
│
├── agents/
│   │
│   ├── agent_1/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── models.py
│   │   └── skills.py
│   │
│   └── agent_2/
│       ├── __init__.py
│       ├── agent.py
│       ├── prompts.py
│       ├── tools.py
│       ├── models.py
│       └── skills.py
│
├── tools/
│   ├── __init__.py
│   ├── file_tools
│   │   ├── __init__.py
│   │   └── file_tools.py
│   └── json_tools
│       ├── __init__.py
│       └── json_tools.py
│
├── models/
│   ├── __init__.py
│   ├── common_models
│   │   ├── __init__.py
│   │   └── common_models.py
│   └── error_models
│       ├── __init__.py
│       └── error_models.py
│
├── skills/
│   ├── __init__.py
│   ├── code_review_skills
│   │   ├── __init__.py
│   │   └── code_review_skills.py
│   └── validation_skills
│       ├── __init__.py
│       └── validation_skills.py
│
├── tests/
│
├── requirements.txt
└── README.md
```