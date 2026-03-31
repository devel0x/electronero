AGENTS.md
👷 Agent Responsibilities
This file outlines the expectations for agents (contributors) working with this repository. Whether you're fixing bugs, adding features, or refactoring code, follow the instructions below before submitting a Pull Request (PR).
🛠️ Compile Instructions
To build the project locally:
•	1. Install dependencies and set up environment
   `sh ubuntu_install.sh`
•	2. Initialize submodules
   `git submodule init`
   `git submodule update`
•	3. Build the project
   `mkdir build`
   `cd build`
   `cmake ..`
   `cd ..`
   `make -j$(nproc)`
•	4. Warnings
   - It's safe to ignore compilation warnings.
   - You may also disable deprecated warnings if they interfere with the build.
•	5. Required Task
   - Important: Make sure you have completed the assigned or requested task before building or compiling.
•	6. Build Failure?
   - If compilation fails, still commit your changes and prepare the PR anyway.
   - The goal is to capture your progress and proposed solution, even if it isn't fully buildable yet.
🧠 Notes
•	Code must be pushed regularly to avoid losing work.
•	PRs should include a brief summary of what was attempted and any remaining blockers.
•	Tag a reviewer once your PR is ready for review, even if the build is incomplete.

Thank you for your contributions. Your work helps move the project forward!
