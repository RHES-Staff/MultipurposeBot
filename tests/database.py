import unittest
import database

class TestDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = database.Database()
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
    
    async def test_database_base(self):
        version = await self.db.fetchone("SELECT sqlite_version();")
        serverOfDepts = await database.discordServers.getAllServersOfDepartments()
        print(f"serverOfDepts: {serverOfDepts}")
        servers = await database.discordServers.getAllRegisteredServers()
        print(f"serverOfDepts: {servers}")
        self.assertTrue(version)

if __name__ == "__main__":
    unittest.main()