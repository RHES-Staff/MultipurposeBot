import logging
import json

import discord

from . import Database

log = logging.getLogger(f"ITskolar.{__name__}")


async def getAllRegisteredServers():
    db = Database()
    servers = []
    for (id,) in await db.fetchall("SELECT id FROM assets_discord_server"):
        servers.append(discord.Object(id=id))
    return servers


async def getAllServersOfDepartments():
    query = """
    SELECT 
        key, 
        full_name, 
        configuration,
        json_group_array(server_id) 
            FILTER (WHERE server_id IS NOT NULL) AS servers
    FROM staff_department
        LEFT JOIN staff_server_departments
            ON staff_department.key = staff_server_departments.department_key
        LEFT JOIN assets_discord_server 
            ON assets_discord_server.id = staff_server_departments.server_id
    GROUP BY key, full_name, configuration;
    """

    db = Database()
    departments = {}
    for key, full_name, configuration, server_ids in await db.fetchall(query):
        departments[key] = {
            "name": full_name,
            "servers": [discord.Object(id=id) for id in json.loads(server_ids)],
        }
    return departments


if __name__ == "__main__":
    print(getAllServersOfDepartments())