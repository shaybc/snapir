"""Validate packaged tool roles without loading driver code into the converter process."""
from zipfile import ZipFile


def check_packaging(driver, server):
    """Require isolated codec classes, JDBC discovery, and separate driver/server paths."""
    with ZipFile(driver) as archive:
        names = archive.namelist()
        registration = archive.read('META-INF/services/java.sql.Driver').decode('utf-8')
        if 'il.co.dcd.fixtures.jdbc.FixtureDriver' not in registration:
            raise ValueError('Fixture driver registration missing')
        if any(name.startswith(('com/fasterxml/', 'org/springframework/', 'il/co/dcd/fixtures/server/')) for name in names):
            raise ValueError('Fixture driver contains application/server library classes')
    with ZipFile(server) as archive:
        if 'il/co/dcd/fixtures/server/FixtureServerCommand.class' not in archive.namelist():
            raise ValueError('Fixture server main class missing')
