# litch

## About
automate itch.io  user side

State? 
**!!- ALPHA ALPHA ALPHA -!!**

## How it works
No credentials are stored, once logged in the session cookie is stored to disk, MFA is supported

Python based, using `requests` and `bs4`

## Features
What is supported?

Automatically 
- download purchases
- claim bundle members

## Usage
#### Log into itch with litch
```
./litch.py --login
```
You will be prompted for your username and password, if you use MFA you will be prompted for the totp code.

Cookies will be saved to `~/.litch/`

#### Claim bundle
```
./litch.py --claim-bundles
```
This will go to your bundles page, get the available links then look for any unclaimed products and attempt to claim them, this will add them to your library which you can then download with the `--download-purchases` option

#### Download Purchases
```
./litch.py --download-purchases
```
This will walk through you purchase pages and download any files your don't already have on disk, default download location is to the current directory. Download location can be overridden with the `--content-path` option

#### Download Purchases to alternate location
```
./litch.py --download-purchases --content-path PATH
```
Downlod your purchase to alternate storage

#### Download Purchase and clean up bad files
```
./litch.py --download-purchases --cleanup-incorrect-files
```
This will use the content-length header and compare to on-disk filesize in bytes to determine if the download is OK

## Known Issues
- Code is very rough at the moment
- We do not handle "Connection reset by peer" at all, if this happens restart the script
- There is no hash available to check validity of download unfortunately so we just get the content-length header from the google cdn (where applicable) and use that to determine if the local file is OK
- Not grabbing any metadata (yet)
