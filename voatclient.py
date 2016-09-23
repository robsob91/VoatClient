#!/usr/bin/env python3

import re, requests, threading, time
try:
    import unicodedata
    from unidecode import unidecode
except:
    pass

class VoatConnectionError(Exception):
    """ Raised when Voat returns a page in HTML format

    This usually happens when there is a connection error or an
    unhandled exception and CloudFlare or Voat return an HTML page
    containing the error description

     * args[0] is a dict containing: "message", "data" and "args"
    """
    pass

class VoatLogInError(Exception):
    """ Raised when logging in fails

    This can be caused by an API that doesn't have a Redirect Url
    configured or an invalid username/password combination

     * args[0] is a dict containing: "message", "data" and "type"
       Possible types are: "invalid key", "invalid password" and
       "invalid redirection"

    Note: type "invalid password" is only raised when third_party is
    True, if third_party is False and a wrong password is used
    VoatTokenError will be raised
    """
    pass

class VoatTokenError(Exception):
    """ Raised when auth or refresh tokens fail to be generated

     * args[0] is a dict containing: "message", "data" and "type"
       Possible types are: "access token not found", "api call failure"
       and "not authenticated"
    """
    pass

class VoatAPICallError(Exception):
    """ Raised when an API call fails

    See Voat documentation for possible errors

     * args[0] is a dict containing: "message" and "data"
    """
    pass

class VoatAPIClient(object):
    """ Base API client class """
    def __init__(self, apiPath, domain="voat.co"):
        """ Initialize self

         * apiPath: api/ for the old API and api/v1/ for the new API
         * domain: usually voat.co but can be api-preview.voat.co for
           testing the new API
        """
        if not apiPath.endswith("/"):
            apiPath = apiPath + "/"
        self.domain = domain
        self.prepend_path = apiPath
        self._headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
            "Host": self.domain,
            "Origin": "https://{}".format(self.domain),
            "Referer": "https://{}/".format(self.domain),
            "User-Agent": "Mozilla/5.0",
            "DNT": "1",
            "Content-Type": "application/json; charset=UTF-8",
        }
        self.session = requests.Session()
    def get_url(self, path=""):
        """ Generate a full URL from a path """
        return "https://{}/{}".format(self.domain, path)
    def call(self, path="", params=None, data=None, method="GET"):
        """ Make an API call and return the parsed JSON

         * path: the relative path of the API call, minus the api/ or
           api/v1/ part
         * params: dict containing GET parameters and their values
         * data: dict containing data to pass, generally used for POST or
           PUT requests
         * method: method to use, can be GET, POST, PUT or DELETE
        """
        path = self.prepend_path + path
        fn = {
            "GET": self.session.get,
            "POST": self.session.post,
            "PUT": self.session.put,
            "DELETE": self.session.delete
        }[method.upper()]
        if data is None:
            ret = fn(self.get_url(path), params=params, headers=self._headers)
        else:
            ret = fn(self.get_url(path), params=params, json=data,
                headers=self._headers)
        try:
            ret = ret.json()
        except Exception as e:
            raise VoatConnectionError({
                "message": "Unexpected (server?) error",
                "data": ret,
                "args": e.args
            })
        return ret

class VoatLegacyClient(VoatAPIClient):
    """ Legacy API client class """
    def __init__(self, domain="voat.co"):
        """ Initialize self

         * domain: usually voat.co but can also be api-preview.voat.co
        """
        super(VoatLegacyClient, self).__init__("api/")

    def get_default_subverses(self):
        """ This API returns a list of default subverses shown to
        guests
        """
        return self.call("defaultsubverses")
    def get_banned_hostnames(self):
        """ This API returns a list of banned hostnames for link type
        submissions
        """
        return self.call("bannedhostnames")
    def get_banned_users(self):
        """ This API returns a list of site-wide banned users """
        return self.call("bannedusers")
    def get_top_200_subverses(self):
        """ This API returns top 200 subverses ordered by subscriber
        count
        """
        return self.call("top200subverses")
    def get_frontpage(self):
        """ This API returns 100 submissions which are currently
        shown on Voat frontpage
        """
        return self.call("frontpage")
    def get_subverse_frontpage(self, subverse):
        """ This API returns 100 submissions which are currently
        shown on frontpage of a given subverse
        """
        return self.call("subversefrontpage", params={"subverse":subverse})
    def get_single_submission(self, submissionId):
        """ This API returns a single submission for a given
        submission ID
        """
        return self.call("singlesubmission", params={"id":submissionId})
    def get_single_comment(self, commentId):
        """ This API returns a single comment for a given comment ID """
        return self.call("singlecomment", params={"id":commentId})
    def get_subverse_info(self, subverseName):
        """ This API returns the sidebar for a subverse """
        return self.call("subverseinfo", params={"subverseName":subverseName})
    def get_user_info(self, userName):
        """ This API returns basic information about a user """
        return self.call("userinfo", params={"userName":userName})
    def get_badge_info(self, badgeId):
        """ This API returns information about a badge

         * badgeId: name of the badge, string, replace spaces with
           underscores
        """
        return self.call("badgeinfo", params={"badgeId":badgeId})
    def get_submission_comments(self, submissionId):
        """ This API returns comments for a given submission ID """
        return self.call("submissioncomments",
            params={"submissionId":submissionId})
    def get_top_100_images_by_date(self):
        """ This API returns the top 100 images """
        return self.call("top100imagesbydate")

class VoatClient(VoatAPIClient):
    """ API v1 client class

    All get_ methods can be used without authentication unless
    specified otherwise
    """
    def __init__(self, apikey, secret=None, username=None, password=None,
        third_party=False, auth_data=None, domain="api.voat.co", autoclean_titles=True):
        """ Initialize self

         * apikey: your public API key
         * secret: your private key
         * username: account name
         * password: I am not a 4th grade teacher, you know what this is
         * third_party: set to True if the username is not the owner of
           the API key, this will perform full OAuth2 authentication, the
           key needs to have a Redirect Url configured.
           Set to False if the username is the owner of the key (this is
           usually the case for bots), no Redirect Url required.
         * auth_data: bypass OAuth2 authentication and use this data
           instead, this is a dict, you can get it after successfully
           logging in once, it is the VoatClient.auth_data property
         * domain: Voat's domain, use preview-api.voat.co for the test
           site, api.voat.co for the real thing or your own domain if you
           are hosting your own Voat clone
         * autoclean_titles: Voat only supports extended ASCII titles
           with no unprintable characters, this will try to approximate
           Unicode titles to their ASCII equivalents, remove redundant
           whitespace and unprintable characters. Warning: it does not
           produce good results when cleaning titles that use the
           cyrillic alphabet
        """
        super(VoatClient, self).__init__("api/v1/", domain)
        self.apikey = apikey
        self.secret = secret
        self.autoclean_titles = autoclean_titles
        self._headers["Voat-ApiKey"] = self.apikey
        self.authenticated = False
        if auth_data:
            self.auth_data = auth_data
            self._headers["Authorization"] = "Bearer {}".format(self.auth_data["access_token"])
            self.refresh_token()
        elif secret and username and password:
            if third_party:
                headers = self._headers.copy()
                headers["Content-Type"] = "text/html; charset=UTF-8"
                s = self.session.get(self.get_url("oauth/authorize"),
                    params={
                        "response_type": "code",
                        "scope": "account",
                        "grant_type": "authorization_code",
                        "client_id": self.apikey
                    }, headers=headers
                )
                if "submit.Signin" not in s.text:
                    raise VoatLogInError({
                        "message": "Invalid API key, make sure your API key has a Redirect Url configured",
                        "data": s,
                        "type": "invalid key"
                    })
                del headers["Content-Type"]
                s = self.session.post(s.url,
                    data={
                        "username": username,
                        "password": password,
                        "submit.Signin": "Sign In"
                    }, headers=headers
                )
                if "submit.Grant" not in s.text:
                    raise VoatLogInError({
                        "message": "Invalid password",
                        "data": s,
                        "type": "invalid password"
                    })
                s = self.session.post(s.url, data={"submit.Grant": "Grant"},
                    headers=headers, allow_redirects=False)
                m = re.match(r'^.*?\?code=(.*)$', s.headers.get("Location", ""))
                if not m:
                    raise VoatLogInError({
                        "message": "Unexpected error, could not get code from URL",
                        "data": s,
                        "type": "invalid redirection"
                    })
                self.authorization_code = m.group(1)
                headers["Content-Type"] = "text/html; charset=UTF-8"
                s = self.session.post(self.get_url("oauth/token"),
                    data={
                        "grant_type": "authorization_code",
                        "code": self.authorization_code,
                        "username": username,
                        "password": password,
                        "client_id": self.apikey,
                        "client_secret": self.secret
                    },
                    headers=headers
                )
                self._get_access_token(s)
            else:
                headers = self._headers.copy()
                headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                data = self.session.post(self.get_url("oauth/token"),
                    data={
                        "grant_type": "password",
                        "username": username,
                        "password": password,
                        "client_id": self.apikey,
                        "client_secret": self.secret
                    },
                    headers=headers
                )
                self._get_access_token(data)

    def call(self, path="", params=None, data=None, method="GET"):
        """ Calls an endpoint and returns the parsed JSON, throws an
        exception if the call returned an error

         * path: the relative path of the API call, minus the api/v1/ part
         * params: dict containing GET parameters and their values
         * data: dict containing data to pass, generally used for POST or
           PUT requests
         * method: method to use, can be GET, POST, PUT or DELETE
        """
        ret = super(VoatClient, self).call(path, params, data, method)
        if not ret["success"]:
            raise VoatAPICallError({
                "message": "API call returned an error",
                "data": ret
            })
        return ret

    def clean_title(self, title):
        """ Cleans a title by converting Unicode characters to their
        ASCII approximations, removes redundant whitespace and unprintable
        characters, trims the title to 200 characters if it is too long
        """
        # Remove zero width spaces
        title = re.sub(r'[\u180e\u200b\ufeff]+', '', title)
        # Replace all consecutive spaces with an ASCII space
        title = re.sub(r'[\s\u2000-\u200a\u202f\u205f]+', ' ', title)
        # Replace the visible space symbols with a similarly looking underscore
        title = re.sub(r'\u2423', '_', title)
        new_title = ""
        # Here is where it gets tricky, do we have both libraries?
        if "unidecode" in globals() and "unicodedata" in globals():
            for c in title:
                # Unidecode tries to use ASCII (0-128) instead of extended ASCII
                # so first we try to get a good extended ASCII replacement using unicodedata and latin1
                ac = unicodedata.normalize('NFKC', c).encode("latin1", "ignore").decode("latin1")
                # if we fail we try unidecode
                if len(ac) == 0:
                    ac = unidecode(c)
                new_title += ac
        elif "unicodedata" in globals():
            # We only have unicodedata, lets just discard all those Russian characters
            new_title = unicodedata.normalize('NFKC', title).encode("latin1", "ignore").decode("latin1")
        elif "unidecode" in globals():
            # We only have unidecode, this should not usually happen, lets try to get those ASCII replacements
            new_title = unidecode(title)
        # Finally get rid of the non printable characters
        new_title = re.sub(r'[^ -~\x80-\xff]', '', new_title)
        # Goodbye spaces
        new_title = new_title.strip()
        # If your length is > 200 get rid of the remaining characters and add [...] at the end
        if len(new_title) > 200:
            new_title = new_title[:194] + " [...]"
        # We are done! I hate you Unicode, go burn in hell and never come back
        return new_title

    def _next_refresh(self):
        """ Refreshes the access token before it expires
        This is an internal method, it is meant to be called in a
        daemon thread
        """
        if self.authenticated:
            time.sleep(self.auth_data["expires_in"]*0.9)
            self.refresh_token()

    def _get_access_token(self, data):
        """ Reads the access token from the JSON data, raises an exception
        on failure, it also starts the _next_refresh thread
        """
        self.authenticated = False
        try:
            auth_data = data.json()
        except Exception as e:
            raise VoatTokenError({
                "message": "Unable to get access token",
                "data": data.text,
                "type": "access token not found"
            })
        if "error" in auth_data:
            raise VoatTokenError({
                "message": "API call failed",
                "data": auth_data,
                "type": "api call failure"
            })
        self.auth_data = auth_data
        self._headers["Authorization"] = "Bearer {}".format(self.auth_data["access_token"])
        self.authenticated = True
        thread = threading.Thread(target=self._next_refresh)
        thread.daemon = True
        thread.start()

    def refresh_token(self, refresh_token=None):
        """ Gets a new access token

         * refresh_token: if it is not None this method will use it as
           the old refresh_token instead of relying on VoatClient.auth_data
        """
        if not self.authenticated and refresh_token is None:
            raise VoatTokenError({
                "message": "You are not authenticated",
                "data": "",
                "type": "not authenticated"
            })
        if refresh_token is None:
            refresh_token = self.auth_data["refresh_token"]
        headers = self._headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        data = self.session.post(self.get_url("oauth/token"),
            data={
                "grant_type":"refresh_token",
                "refresh_token":refresh_token,
                "client_id":self.apikey,
                "client_secret":self.secret
            },
            headers=headers
        )
        self._get_access_token(data)
        return self.auth_data

    # Search Options
    def build_search_options(self, span=None, sort=None, direction=None,
        date=None, count=None, index=None, page=None, search=None):
        """ Simplifies building the search options dict that can be used to
        search/sort submissions and comments, it is here as a convenient
        way to get parameter names on IDEs. All parameters are strings

         * span: time span, can be one of: all, hour, day, week, month,
           quarter or year
         * sort: sorting algorith, can be one of: new, top, rank,
           relativerank, active, viewed, discussed, bottom or intensity
         * direction: sort direction, can be one of: default or reversed
         * date: date in ISO 8601 format
         * count: number of records requested, maximum of 50
         * index: current index to start from for search results
         * page: page to retrieve, overrides index and calculates it for you
         * search: value to match for submissions or comments
        """
        o = {}
        if span is not None:
            o["span"] = span
        if sort is not None:
            o["sort"] = sort
        if direction is not None:
            o["direction"] = direction
        if date is not None:
            o["date"] = date
        if count is not None:
            o["count"] = date
        if index is not None:
            o["index"] = date
        if page is not None:
            o["page"] = date
        if search is not None:
            o["search"] = date
        return o

    # System
    def get_system_banned_domains(self):
        """ Gets Voat's currently banned domain list """
        return self.call("system/banned/domains")
    def get_system_status(self):
        """ Gets the current operational state of the API """
        return self.call("system/status")
    def get_system_time(self):
        """ Gets the current time on the server. Use this to
        calculate offsets in your application
        """
        return self.call("system/time")

    # Submissions
    def get_submissions(self, subverse, searchOptions=None):
        """ Get submissions from a subverse

        Use _any to get from all non private subverses and _front
        for your frontpage
        _any is like all but it doesn't honor block lists or minccp
        """
        return self.call("v/{}".format(subverse), params=searchOptions)
    def post_submission(self, subverse, title, content=None, url=None,
        isAdult=False, isAnonymized=False):
        """ Posts a new submission to the specified subverse """
        if self.autoclean_titles:
            title = self.clean_title(title)
        data = {
            "title": title,
            "isAdult": isAdult,
            "isAnonymized": isAnonymized
        }
        if url:
            data["url"] = url
        elif content:
            data["content"] = content
        return self.call("v/{}".format(subverse), data=data, method="POST")

    # Submission
    def delete_submission(self, submissionID, subverse=None):
        """ Deletes a submission """
        if subverse is not None:
            return self.call("v/{}/{}".format(subverse, submissionID),
                method="DELETE")
        return self.call("submissions/{}".format(submissionID), method="DELETE")
    def get_submission(self, submissionID, subverse=None):
        """ Gets a single submission by ID """
        if subverse is not None:
            return self.call("v/{}/{}".format(subverse, submissionID))
        return self.call("submissions/{}".format(submissionID))
    def put_submission(self, submissionID, subverse=None, title=None,
        content=None, url=None, isAdult=False, isAnonymized=False):
        """ Edits a submission

        Title changes are only accepted during the first 10 minutes
        """
        data = {
            "isAdult": isAdult,
            "isAnonymized": isAnonymized
        }
        if title:
            if self.autoclean_titles:
                title = self.clean_title(title)
            data["title"] = title
        if url:
            data["url"] = url
        elif content:
            data["content"] = content
        if subverse is not None:
            return self.call("v/{}/{}".format(subverse, submissionID),
                data=data, method="PUT")
        return self.call("submissions/{}".format(submissionID),
            data=data, method="PUT")

    # Subverse
    def get_subverse_info(self, subverse):
        """ Retrieves subverse information """
        return self.call("v/{}/info".format(subverse))
    def post_subverse_block(self, subverse):
        """ Blocks a subverse """
        return self.call("v/{}/block".format(subverse), method="POST")
    def delete_subverse_block(self, subverse):
        """ Unblocks a previously blocked subverse """
        return self.call("v/{}/block".format(subverse), method="DELETE")
    def get_subverse_defaults(self):
        """ Gets Voat's current Default Subverse list """
        return self.call("subverse/defaults")
    def get_subverse_new(self):
        """ Gets Voat's Newest Subverses """
        return self.call("subverse/new")
    def get_subverse_top(self):
        """ Gets Voat's Top Subverses by Subscriber count """
        return self.call("subverse/top")
    def get_subverse_search(self, phrase):
        """ Searches Voat's Subverse catalog for search phrase """
        return self.call("subverse/search", params={"phrase":phrase})

    # Comments
    def get_comments(self, subverse, submissionID, parentID=None, index=None,
        searchOptions=None):
        """ Gets comments for a submission starting from a specified
        parent comment (optional) starting at a specified index (optional)

        Supports Search Options querystring arguments
        """
        if index and parentID:
            return self.call("v/{}/{}/comments/{}/{}".format(subverse,
                submissionID, parentID, index), params=searchOptions)
        elif parentID:
            return self.call("v/{}/{}/comments/{}".format(subverse,
                submissionID, parentID), params=searchOptions)
        return self.call("v/{}/{}/comments".format(subverse, submissionID),
            params=searchOptions)

    # Comment
    def delete_comment(self, commentID):
        """ Deletes an existing comment """
        return self.call("comments/{}".format(commentID), method="DELETE")
    def get_comment(self, commentID):
        """ Retrieves a single comment """
        return self.call("comments/{}".format(commentID))
    def post_comment(self, value, subverse=None, submissionID=None, commentID=None):
        """ Post a reply to an existing comment

        Use the subverse and submissionID parameters to reply to a
        submission. Use the commentID parameter to reply to comments.
        """
        if subverse is not None and submissionID is not None:
            if commentID is not None:
                return self.call("v/{}/{}/comment/{}".format(subverse,
                    submissionID, commentID), data={"value":value},
                    method="POST")
            return self.call("v/{}/{}/comment".format(subverse,
                submissionID), data={"value":value}, method="POST")
        if commentID is not None:
            return self.call("comments/{}".format(commentID),
                data={"value":value}, method="POST")
        raise VoatAPICallError({
            "message": "You must provide at least the comment or submission ID",
            "data": ""
        })
    def put_comment(self, commentID, value):
        """ Edits an existing comment """
        return self.call("comments/{}".format(commentID), data={"value":value},
            method="PUT")

    # User
    def post_user_block(self, user):
        """ Blocks a user. Blocks hide a blocked user’s submissions,
        comments, and messages from appearing.
        """
        return self.call("u/{}/block".format(user), method="POST")
    def delete_user_block(self, user):
        """ Unblocks a previously blocked user """
        return self.call("u/{}/block".format(user), method="DELETE")
    def get_user_info(self, user):
        """ Retrieves user information """
        return self.call("u/{}/info".format(user))
    def get_user_comments(self, user):
        """ Get comments for a user

        Supports Search Options querystring arguments
        """
        return self.call("u/{}/comments".format(user))
    def get_user_submissions(self, user):
        """ Gets submissions for a user

        Supports Search Options querystring arguments
        """
        return self.call("u/{}/submissions".format(user))
    def get_user_subscriptions(self, user=None):
        """ Gets subscriptions for a user

        Authentication Required
        """
        if user is None:
            return self.call("u/subscriptions")
        return self.call("u/{}/subscriptions".format(user))
    def get_user_saved(self):
        """ Gets saved items for current user

        Authentication Required
        """
        return self.call("u/saved")
    def get_user_blocked_subverses(self):
        """ Gets blocked subverses for current user

        Authentication Required
        """
        return self.call("u/blocked/subverses")
    def get_user_blocked_users(self):
        """ Gets blocked users for current user

        Authentication Required
        """
        return self.call("u/blocked/users")

    # UserPreferences
    def get_preferences(self):
        """ Retrieves user preferences

        Authentication Required
        """
        return self.call("u/preferences")
    def put_preferences(self, preferences):
        """ Updates a user's preferences """
        return self.call("u/preferences", data=preferences, method="PUT")

    # UserMessages
    def post_messages_reply(self, messageID, value):
        """ Replies to a user message """
        return self.call("u/messages/reply/{}".format(messageID),
            data={"value":value}, method="POST")
    def get_messages(self, mtype, state):
        """ Gets messages for the logged in user

         * mtype: message type, can be one of: inbox, sent, comment,
           submission, mention or all
         * state: message state, can be one of: unread, read or all

        Authentication Required
        """
        return self.call("u/messages/{}/{}".format(mtype, state))
    def post_messages(self, message, recipient, subject):
        """ Sends a new Private Message to a user """
        return self.call("u/messages", data={
            "message": message, "recipient": recipient, "subject": subject
        }, method="POST")

    # Vote
    def post_vote(self, vtype, vid, vote, revokeOnRevote=None):
        """ Submit votes of a user

         * vtype: vote type, can be one of: comment or submission
         * vid: comment/submission ID to vote
         * vote: -1 (downvote), 0 (revoke), 1 (upvote)
         * revokeOnRevote: True: revoke, False: ignore duplicate
           default is True if not present
        """
        if revokeOnRevote is not None:
            return self.call("vote/{}/{}/{}".format(vtype, vid, vote),
                params={
                    "revokeOnRevote":{True:"true",False:"false"}[revokeOnRevote]
                }, method="POST")
        return self.call("vote/{}/{}/{}".format(vtype, vid, vote),
            method="POST")

    # Save
    def post_submissions_save(self, submissionID):
        """ Saves a submission to a users saved items collection """
        return self.call("submissions/{}/save".format(submissionID),
            method="POST")
    def delete_submissions_save(self, submissionID):
        """ Deletes a saved submission from a users saved item collection """
        return self.call("submissions/{}/save".format(submissionID),
            method="DELETE")
    def post_comments_save(self, commentsID):
        """ Saves a comment to a users saved items collection """
        return self.call("comments/{}/save".format(commentsID),
            method="POST")
    def delete_comments_save(self, commentsID):
        """ Deletes a saved comment from a users saved items collection """
        return self.call("comments/{}/save".format(commentsID),
            method="DELETE")

    # Stream
    def get_stream_submissions(self):
        """ Returns a stream of submissions since the last call made to
        this endpoint. Used for live monitoring.

        Authentication Required
        """
        return self.call("stream/submissions")
    def get_stream_comments(self):
        """ Returns a stream of comments since the last call made to this
        endpoint. Used for live monitoring.

        Authentication Required
        """
        return self.call("stream/comments")
