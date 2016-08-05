# VoatClient

This is a Python wrapper for the Voat APIs, both the legacy and the new API. It supports all OAuth2 authentication methods used by Voat's API and all the API calls are properly wrapped. Avatar uploading and some of the preferences in [api/v1/u/preferences](https://preview-api.voat.co/Help/Api/PUT-api-v1-u-preferences) have not been implemented on Voat yet, please make sure to check [/v/announcements](https://voat.co/v/announcements) and [/v/PreviewAPI](https://voat.co/v/PreviewAPI) regularly, this client may need an update once they are implemented.

## Known bugs

Method `clean_title` of `VoatClient` does its best to convert Unicode to its  ASCII equivalent but the implementation is just a hack and Russian text is not properly converted. Better implementations are welcome.

## Future

Unfortunately I'm not planning on updating or continue developing this so I upload it here hoping someone forks it and improves it. Once the API goes live line 188 will have to be updated with the new domain, it is also very likely that the legacy API will be completely removed from Voat so that whole class will have to be erased too.
