help me plan and design a multi-agent architecture using Google's ADK to transform an IBM Composer based monolith with about 1000+ operations (services) into a separated java micro-services with spring boot that are deployed to Open-shift as kubernetese objects.

the code transform should map and include all the source files and definitions involved in each operation (including but not only: formats, opSteps, dbAccessors, context ...).

break down the process into several tasks that should help to achieve the goal in a stable and more deterministic manner, for instance it might be broken down into the following steps:
1. generating a list of operation names including metadata like the xml file they are defined at, their tag name in order to understand what operations exists and generate a list the the agents can loop through.
2. convert the operation flow logic into native java code so it can be transformed later into spring-boot micro-service.
3. map each operation and find the xml tags that it uses and rely on (formats, opSteps, context ...)
4. map each xml tag that the operation use  (extracted in step 3) into it's java implementation (if relevant) and convert it into native java class. this native java class can be used in this operation and in some other operations that uses this opStep (or some other tag) and will be converted by the agents, so there is a reuse of code and not duplication of implementation of the same xml tags again and again during the transformation process. use the dse.ini files to find out what javaclass implements this tag and use it in order to implement the native java class.
5. once each operation has a flow code that uses native java classes and code to receive and reply with the exact xml request and response formats - create a spring-boot micro-service that is free of ibm component composer code and does not rely on ibm websphere application server.

adk design architecture rules:
- create a hierarchical agent structure, break down the flow into sub agents and tasks, use appropriate adk patterns when needed (Sequential, Parallel, Coordinator, Dispatcher, Loop, Generator-Critic (Review), Human-in-the-Loop, Agent-as-Tool ...)
- each agent can use sub agents to break it's own task into smaller parts
- each agent should focus on one particular task (keep it as small as possible like read a file, convert to java, write to a file, check it compiles ...) if the task is to big break it into even smaller sub tasks and use sub agents and tools
- do not use cloud and online tools or websites (including adk builtin tools), the adk multi-agent architecture will use a local LLM and will run in an offline environment
- make sure delegation and responsibility flow between agents is deterministic and fully covered, generate a mermaid diagram showing: all agents as nodes, data/control flow as directed edges with labels, orchestrator agents clearly marked, external tools/APIs shown as leaf nodes
- verify agent communication is sound clear and has unique ids for state storage so two agent instances working on two different operations or classes will not overwrite each others state data.
- save session and adk data into database so a run can continue from the last place it was cancelled
- use top level constants for general values (agent model to use, model base url, max loop retries, composer root code folder, path to save the resulting microservices code ...)
- use python as the adk implementation language
- use LiteLLM in order to call the model
- maintain each agent in it's own separated folder and scaffold a folder structure that will make sense and help maintain and understand all the agents in the architecture and their role and relationships
- maintain each tool in its own file under tools folder, and group related tools together into the same file or several tool files into the same folder
- try not to put more then 20 tools or agents in the same folder
- you MUST keep files under 500 lines, if they reach 500 lines- break them down into a separeted files
- reffere to the attached files: adk multi-agent architect Skill.md, adk-tools.md, adk-patterns.md for more information

wsbcc code transformation rules:
- all the resulting code must be native java with spring-boot.
- all the resulting code must not use or rely on IBM Websphere Business Component Composer (WSBCC) code or libraries.
- all the resulting code must not use or rely on IBM Websphere Application Server (WAS) code or libraries. and does not require WAS to run.
- existing classes that are used in more then one place in the code should be implemented in a separated file and class and stored in a common jar that the micro-services can import and use.
- existing format structures that are used in more then one operation or opStep should be implemented in a separate file and class so they can be reused and maintained in a single point (for instance a request header should be declared only once and used in all operations)
- reffere to the attached file: wsbcc_developer_manual.md for further information on the composer (WSBCC monolith server)