# Multipurpose Bot
It can handle **everything**.

## Setup
This assumes that the user has prior knowledge in handling Python, Git, and a SQLite Database.
1. Fill up .env
2. Create a Discord Bot and configure its OAuth and Servers.
3. For Development Cog: Create a Bug Report channels (can be multiple), Leaderboard Channel Logs channel, Tester Role. Head of Tester Role, and Developer Role. copy their IDs
4. Run `main.py`, to autogenerate `app.db`, it's expected to crash.
5. In `app.db`, fill this JSON up with the IDs and put it in the `staff_department.configuration.dev`. Ensure it's stored in JSONB.
```
{
    "testing_guild": devserver.id,
    "bug_report_channels": [devserver_channels["bug-reports"].id],
    "tester_role": devserver_tester_role.id,
    "head_of_tester_role": devserver_head_tester_role.id,
    "developer_role": devserver_dev_role.id,
    "minimum_report_quota": 6,
    "leaderboard_channel": devserver_channels["leaderboards"].id,
    "leaderboard_message": 0,
    "logging_channel": devserver_channels["logs"].id,
    "start_of_week": 0,
}
```
6. In `app.db`, append `staff_department.servers.dev` with the server ID of the server you joined the bot in. ensure `staff_department.servers.dev == staff_department.confi.dev`
## Copyright
Property of Hydroelectric Simulator.

