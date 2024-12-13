# Refractory

A server for running multiple foundry instances across multiple versions.

## Notes on Foundry Licenses

Foundry licensing requires that only a single instance is available for use by players under a single license key.

Refractory will keep this requirement fulfilled by assoicating each running instance with a license key. These keys
are stored in the application's database.

When an instance is launched, it will attempt to associate a license key in the application's database with that instance.
Any key not currently in use by an instance will be valid for movement between instances.
Additionally, any key in use by an instance with no active players on it will be considered valid for movement between instances, 
though that instance will be automatically shut down before the license is moved.

## To-do

Initial Release
- [X] Core Reverse Proxy and Login Management
- [ ] License Management and Corresponding Pages
- [ ] Version/Release Management and Corresponding Pages
- [ ] Instance Management and Corresponding Pages
- [ ] Invite Management and Corresponding Pages
- [ ] User Management and Corresponding Pages

Nice-to-haves
- [ ] Standard User Features - Password change forgot password
- [ ] Barebones non-managed mode
- [ ] Discord auth?

## Projects used

[Foundry Portal](https://github.com/Daxiongmao87/foundry-portal)
[leveldb.py](https://github.com/jtolio/leveldb-py)

(Project licenses are included in the `licenses/` directory)