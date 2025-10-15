# Refractory

Managed FoundryVTT instances for self-hosted setups, including an alternate auth system.

Meant to be run as a container; running the server outside of a container for non-development purposes is discouraged and won't be supported.

## Notes on Release Status

The current version of refractory is still in its alpha phase. While much of the core functionality exists, the server administrator still
needs to be involved heavily for use of the server, and interaction with the default django admin panel is necessary for some operations.

The current UI also focuses on barebones functionality over niceties, and is likely to change.

Until the container images are published to a registry, migrations will be squashed into an initial migration file.

## Notes on Foundry Licenses

Foundry licensing requires that only a single instance is available for use by players under a single license key.

Refractory will keep this requirement fulfilled by assoicating each running instance with a license key. These keys
are stored in the application's database.

When an instance is launched, it will attempt to associate a license key in the application's database with that instance.
Any key not currently in use by an instance will be valid for movement between instances.
Additionally, any key in use by an instance with no active players on it will be considered valid for movement between instances,
though that instance will be automatically shut down before the license is moved.

## To-do

Initial Release:

- [X] Core Reverse Proxy and Login Management
- [ ] License Management and Corresponding Pages
- [X] Version/Release Management and Corresponding Pages
- [X] Instance Management and Corresponding Pages
- [ ] Invite Management and Corresponding Pages
- [X] Player/GM Registration
- [X] Group Management
- [ ] Instance Configuration Button
- [ ] Basic User and Player Management (delete/disable/password reset without admin panel?)
- [X] Action for releasing container images to a registry

Nice-to-haves:

- [ ] Standard User Features - Password change, forgot password
- [ ] Barebones non-managed mode
- [ ] In-depth desync protection (prevent user passwords from being changed, etc)
- [ ] Instance importing
- [ ] Cleanup of removed instances/versions
- [ ] Smarter management of extracted foundry versions - zip file should be the authoritative artifact
- [ ] Discord auth as secondary or alternate login

## Open-Source Projects Pulled into Source

The following projects have been pulled into this project's source.

- [Foundry Portal](https://github.com/Daxiongmao87/foundry-portal) - Heavily modified to be used as html/css templates.

(Full project licenses are included in the `licenses/` directory)
