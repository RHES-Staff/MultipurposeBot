# Multipurpos Bot - Architecture
This is a service for the Hydroelectric Simulator that is designed to be a core part of its infrastructure.

## Services
Currently, it serves 2 major services:
- Bug Logger (used by the Development Department and Testing Team)
- [Staffpanelicious](https://github.com/RHES-Staff/Staffpanelicious) - API (used by the Board of Directors and Department Heads)

In addition, it also services 1 minor service:
- Trainee Feedback (used by the Systems Department)

## Overall Layout
The project is structured in this way:
```
MultipurposeBot/
├── api/                - REST API Handlers for Staffpanelicious
├── assets/             - Assets that is commonly used
├── database/           - Common Database Operations between API and Bot 
├── features/           - Discord Bot Handlers
│   └── views/          - UI Elements for Bot
├── tests/      
│   ├── integration/    - Integration Tests for both Discord and API Layer
│   ├── media/          - Media that is used by the tests
│   └── unit/           - Unit Tests, primarily for Database operations 
├── app.db              - SQLite Database for the whole system 
├── logging.json        - Logging Configuration
└── main.py             - Main Entrypoint
```
The app is split up in 2 major components: a discord.py bot (`main.MultipurposeBot` class), and a FastAPI server (`main.init_api()`). To cooperate with discord.py being an asyncio-reliant library, the application is in asynchronous execution.

## Discord.py Handlers
`main.MultipurposeBot` is the main working handler of the Discord component. There are some helper functions included in the bot itself.

discord.py has no native cached checks fallback on API if none found function, so `MultipurposeBot` impelmented it via `cached_fetch_x` functions, This is to minimize API calls and to make the lives of the programmer easier :3

`MultipurposeBot` uses discord.py's Cog system to dynamically add extensions to the system. This is especially useful for the early development of the app (business requirements change everyday at this point) and for separation of concern. Requirements of departments can be added/removed dynamically just by removing modules in features/.

`MultipurposeBot` also has some helpers for fire-and-forget asynchronous operations through a worker function. This is used to (hopefully) speed up the main loop of the component.

## Discord.py Cogs
Cogs (as i'll call them in this document) are the modules that compose features/, they are arranged per the department that requires a specific functionality be in the bot. 

Every Cog has their own dynamic configuration that's dictated by their own needs, stored in the database in `staff_departments.configuration` that is fetched by a cog before it starts up. Filling up the database first with the appropriate data (as dictated in the README.md and its associated cog documentation) is crucial for the bot to start up. 

There's plans to let the cogs soft-fail if it failed due to a misconfiguration, but it's not yet built.

Every cog can also be configured to only run on a specific server. It is is stored in `staff_department.servers` as a list of Guild IDs. It is imperative that it's properly filled up before starting.

## FastAPI Handlers
`main.init_api` initializes the FastAPI handler for the API component. Similar to how `MultipurposeBot` handles extensions, files in /api can also be dynamically changed. The files are arranged by their API Path (queries inside /api/department/* goes in api/department.py)

## Database
`database/core.py` contains `Database` class, the main wrapper for any Database operation. It is abstracted away to make potential migrations to other databases (like PostgreSQL) easier. Currently, it uses `aiosqlite` to handle the actual operations.

Documentation about the schema can be found in 02-schema.md

The whole folder contains a lot of database operations that is commonly used between them. All operations regarding them return a custom dataclass object, defined in `database/models.py`. This is to standardize how common objects (like staff) are used and accessed by both Discord and API components.

## Testing
Unit Testing and Integration Testing is a hot mess at this moment, and is being rewritten. Unit tests all focus on the common database/ operations, while Integration Tests all focus on the features/ functionality.

Due to limitations regarding Integration Testing with discord.py and dpytest, running the tests requires a custom patch of dpytest 0.7.0 in order to make it work with reactions and file uploads. Please contact [bonnyyyy](https://github.com/bonaktan) if you want the integration tests to run properly.