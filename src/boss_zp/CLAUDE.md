# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## High-level code architecture and structure

This is a TypeScript project that implements a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server named `mcp-boss-zp`. The server allows a large language model to interact with the Boss Zhipin (Boss 直聘) API to search for jobs and send greetings to recruiters.

The core logic is in `src/main.ts`, which initializes an `McpServer` and defines three resources:

1.  **`boss-zp-greeting`**: Handles URIs like `boss-zp://greeting/{securityId}/{jobId}` to send a greeting for a specific job.
2.  **`boss-zp-recommendJobs`**: Handles URIs like `boss-zp://recommendJobs/{page}/{encryptExpectId}/{experience}/{jobType}/{salary}` to fetch recommended job listings. It supports pagination and filtering.
3.  **`boss-zp-getConfig`**: Handles `boss-zp://getConfig` to provide configuration data (e.g., mappings for experience, job type, salary) for job searches.

The server communicates using `StdioServerTransport`, meaning it uses standard input/output for communication.

Business logic is separated into the `src/api/` directory:

*   `src/api/jobLists.ts`: Contains the logic to fetch job lists.
*   `src/api/greetBoss.ts`: Contains the logic for sending greetings.
*   `src/api/fetch.ts`: A generic fetch wrapper for making HTTP requests to the Boss Zhipin API.

## Commonly used commands

*   **Build the project**:
    ```bash
    pnpm build
    ```
    This command compiles the TypeScript code from `src/` into JavaScript in the `dist/` directory and makes the output files executable.

*   **Run the server (as per `readme.md` instructions for MCP clients)**:
    ```bash
    npx -y mcp-boss-zp
    ```
    This command requires environment variables `COOKIE` and `BST` to be set for authentication with the Boss Zhipin API.
