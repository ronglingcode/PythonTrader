import os
import time
import json
import pprint
import datetime
import pathlib
import requests
import urllib.parse

from typing import Any
from typing import Dict
from typing import List
from typing import Union
from typing import Optional
from datetime import timedelta

from td.utils import StatePath
from td.utils import TDUtilities

from td.orders import Order
from td.orders import OrderLeg
from tos.stream import TDStreamerClient
from td.option_chain import OptionChain

from td.enums import VALID_CHART_VALUES
from td.enums import ENDPOINT_ARGUMENTS

from td.oauth import run
from td.oauth import shutdown
from td.app.auth import FlaskTDAuth

from td.exceptions import TknExpError
from td.exceptions import ExdLmtError
from td.exceptions import NotNulError
from td.exceptions import ForbidError
from td.exceptions import NotFndError
from td.exceptions import ServerError
from td.exceptions import GeneralError

class TDClient():
    def __init__(self, credentials_path: str = None, 
                       auth_flow: str = 'default', _do_init: bool = True, _multiprocessing_safe = False) -> None:
        # Define the configuration settings.
        self.config = {
            'cache_state': True,
            'api_endpoint': 'https://api.tdameritrade.com',
            'api_version': 'v1',
            'auth_endpoint': 'https://auth.tdameritrade.com/auth',
            'token_endpoint': 'oauth2/token',
            'refresh_enabled': True
        }
        
        ts = (datetime.datetime.now() + timedelta(days=1)).timestamp()
        with open(credentials_path) as f:
            data = json.load(f)
            self.state = {
                'access_token': data['access_token'],
                'refresh_token': data['refresh_token'],
                'refresh_token_expires_at':ts, 
                'access_token_expires_at':ts,
                'logged_in': True
            }
            self.client_id = data['client_id']
        self._cached_state = None
        self._multiprocessing_safe = _multiprocessing_safe
        self._multiprocessing_lock = None

        return
        # Define the initalized state, these are the default values.
        self.state = {
            'access_token': None,
            'refresh_token': None,
            'logged_in': False
        }
        
        if self._multiprocessing_safe:
            import multiprocessing as mp
            self._cached_state = mp.Manager().dict()
            self._multiprocessing_lock = mp.Lock()
            self._cached_state.update({
                'access_token': None,
                'refresh_token': None,
                'logged_in': False
            })

        self.auth_flow = auth_flow
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.account_number = account_number
        
        self.credentials_path = pathlib.Path(credentials_path)
        self._td_utilities = TDUtilities()

        if self.auth_flow == 'flask':
            self._flask_app = FlaskTDAuth(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                credentials_file=self.credentials_path
            )
        else:
            self._flask_app = None
        
        # define a new attribute called 'authstate' and initialize to `False`. This will be used by our login function.
        self.authstate = False

        # call the state_manager method and update the state to init (initalized)
        if _do_init:
            self._state_manager('init')

        # Initalize the client with no streaming session.
        self.streaming_session = None

    def __repr__(self) -> str:
        """String representation of our TD Ameritrade Class instance."""

        # define the string representation
        str_representation = '<TDAmeritrade Client (logged_in={login_state}, authorized={auth_state})>'.format(
            login_state=self.state['logged_in'],
            auth_state=self.authstate
        )

        return str_representation

    def _headers(self, mode: str = None) -> dict:
        """Create the headers for a request.
        Returns a dictionary of default HTTP headers for calls to TD Ameritrade API,
        in the headers we defined the Authorization and access token.
        ### Arguments:
        ----
        mode {str} -- Defines the content-type for the headers dictionary. (default: {None})
        
        ### Returns:
        ----
        {dict} -- Dictionary with the Access token and content-type
            if specified
        """

        # create the headers dictionary
        headers = {
            'Authorization': 'Bearer {token}'.format(token = self.state['access_token'])
        }

        if mode == 'json':
            headers['Content-Type'] = 'application/json'
        elif mode == 'form':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        return headers

    def _api_endpoint(self, endpoint: str, resource: str = None) -> str:
        """Convert relative endpoint (e.g., 'quotes') to full API endpoint.
        ### Arguments:
        ----
        endpoint {str} -- The URL that needs conversion to a full endpoint URL.
        resource {str} -- The API resource URL that you want to request. (default: {None})
        ### Returns:
        ----
        {str} -- A full url that specifies a valid endpoint.
        """

        # Define the parts.
        if resource:
            parts = [resource, self.config['api_version'], endpoint]
        else:
            parts = [self.config['api_endpoint'], self.config['api_version'], endpoint]

        # Built the URl
        return '/'.join(parts)

    def _state_manager(self, action: str) -> None:
        """Manages the session state.
        Manages the self.state dictionary. Initalize State will set
        the properties to their default value. Save will save the 
        current state if 'cache_state' is set to TRUE.
        ### Arguments:
        ----
        action {str}: action argument must of one of the following:
            'init' -- Initalize State.
            'save' -- Save the current state.
        """

        credentials_file_exists = self.credentials_path.exists()

        # if they allow for caching and the file exists then load it.
        if action == 'init' and credentials_file_exists:
            with open(file=self.credentials_path, mode='r') as json_file:
                self.state.update(json.load(json_file))
                if self._multiprocessing_safe:
                    self._cached_state.update(self.state)

        # if they want to save it and have allowed for caching then load the file.
        elif action == 'save':     
            with open(file=self.credentials_path, mode='w+') as json_file:
                if self._multiprocessing_safe:
                    json.dump(obj=dict(self._cached_state), fp=json_file, indent=4)
                else:
                    json.dump(obj=self.state, fp=json_file, indent=4)

    def login(self) -> bool:
        """Logs the user into the TD Ameritrade API.
        Ask the user to authenticate  themselves via the TD Ameritrade Authentication Portal. This will
        create a URL, display it for the User to go to and request that they paste the final URL into
        command window. Once the user is authenticated the API key is valide for 90 days, so refresh
        tokens may be used from this point, up to the 90 days.
        ### Returns:
        ----
        {bool} -- Specifies whether it was successful or not.
        """

        # Only attempt silent SSO if the credential file exists.
        if self.credentials_path.exists() and self._silent_sso():
            self.authstate = True
            return True
        else:
            self.oauth()
            self.authstate = True
            return True
        
        if self._flask_app and self.auth_flow == 'flask':
            run(flask_client=self._flask_app, close_after=True)

    def logout(self) -> None:
        """Clears the current TD Ameritrade Connection state."""

        # change state to initalized so they will have to either get a
        # new access token or refresh token next time they use the API
        self._state_manager('init')

    def grab_access_token(self) -> dict:
        """Refreshes the current access token.
        This takes a valid refresh token and refreshes
        an expired access token. This is different from
        exchanging a code for an access token.
        ### Returns:
        ----
        {bool} -- `True` if successful, `False` otherwise.
        """

        # build the parameters of our request
        data = {
            'client_id': self.client_id,
            'grant_type': 'refresh_token',
            'refresh_token': self.state['refresh_token']
        }

        # Make the request.
        response = requests.post(
            url="https://api.tdameritrade.com/v1/oauth2/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=data
        )

        if response.ok:

            self._token_save(
                token_dict=response.json(),
                includes_refresh=False
            )

    def grab_refresh_token(self) -> bool:
        """Grabs a new refresh token if expired.
        
        This takes a valid refresh token and requests
        a new refresh token along with an access token.
        This is similar to `grab_access_token` but it 
        does not include the `access_type` argument.
        Which specifies to return a new refresh token
        along with an access token.
        ### Returns:
        ----
        {bool} -- `True` if successful, `False` otherwise.
        """

        # build the parameters of our request
        data = {
            'client_id': self.client_id,
            'grant_type': 'refresh_token',
            'access_type': 'offline',
            'refresh_token': self.state['refresh_token']
        }

        # Make the request.
        response = requests.post(
            url="https://api.tdameritrade.com/v1/oauth2/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=data
        )

        if response.ok:

            self._token_save(
                token_dict=response.json(),
                includes_refresh=True
            )

            return True

    def grab_url(self) -> dict:
        """Builds the URL that is used for oAuth."""

        # prepare the payload to login
        data = {
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id + '@AMER.OAUTHAP'
        }

        # url encode the data.
        params = urllib.parse.urlencode(data)

        # build the full URL for the authentication endpoint.
        url = "https://auth.tdameritrade.com/auth?" + params

        return url

    def oauth(self) -> None:
        """Runs the oAuth process for the TD Ameritrade API."""

        # Create the Auth URL.
        url = self.grab_url()

        # Print the URL.
        print(
            'Please go to URL provided authorize your account: {}'.format(url)
        )

        # Paste it back and store it.
        self.code = input(
            'Paste the full URL redirect here: '
        )

        # Exchange the Code for an Acess Token.
        self.exchange_code_for_token(
            code=self.code,
            return_refresh_token=True
        )

    def exchange_code_for_token(self, code: str, return_refresh_token: bool) -> dict:
        """Access token handler for AuthCode Workflow.
        ### Overview:
        ----
        This takes the authorization code parsed from
        the auth endpoint to call the token endpoint
        and obtain an access token.
        ### Returns:
        ----
        {bool} -- `True` if successful, `False` otherwise.
        """

        # Parse the URL
        url_dict = urllib.parse.parse_qs(self.code)

        # Grab the Code.
        url_code = list(url_dict.values())[0][0]

        # Define the parameters of our access token post.
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id + '@AMER.OAUTHAP',
            'code': url_code,
            'redirect_uri': self.redirect_uri
        }

        if return_refresh_token:
            data['access_type'] = 'offline'

        # Make the request.
        response = requests.post(
            url="https://api.tdameritrade.com/v1/oauth2/token",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data=data
        )
        
        if response.ok:

            self._token_save(
                token_dict=response.json(),
                includes_refresh=True
            )

            return True

    def validate_token(self, already_updated_from_cache=False) -> bool:
        """Validates whether the tokens are valid or not.
        ### Returns
        -------
        bool
            Returns `True` if the tokens were valid, `False` if
            the credentials file doesn't exist.
        """

        if 'refresh_token_expires_at' in self.state and 'access_token_expires_at' in self.state:

            # Grab the Expire Times.
            refresh_token_exp = self.state['refresh_token_expires_at']
            access_token_exp = self.state['access_token_expires_at']

            refresh_token_ts = datetime.datetime.fromtimestamp(refresh_token_exp)
            access_token_ts = datetime.datetime.fromtimestamp(access_token_exp)

            # Grab the Expire Thresholds.
            refresh_token_exp_threshold = refresh_token_ts - timedelta(days=2)
            access_token_exp_threshold = access_token_ts - timedelta(minutes=5)

            # Convert to Seconds.
            refresh_token_exp_threshold = refresh_token_exp_threshold.timestamp()
            access_token_exp_threshold = access_token_exp_threshold.timestamp()

            # See if we need a new Refresh Token.
            if datetime.datetime.now().timestamp() > refresh_token_exp_threshold:
                if self._multiprocessing_safe and not already_updated_from_cache:
                    # ONLY ONE PROCESS / THREAD CAN GET A NEW TOKEN AT THE SAME TIME! Update from cache then revalidate!
                    # Only using the multiprocessing cache here prevents added latency checking cross process values
                    #  except when the token has expired, which should only be once every 30 minutes. Better than making
                    #  state a full MP dict.
                    with self._multiprocessing_lock:
                        self.state.update(dict(self._cached_state))
                        self.validate_token(already_updated_from_cache=True)
                else:
                    print("Grabbing new refresh token...")
                    self.grab_refresh_token()

            # See if we need a new Access Token.
            if datetime.datetime.now().timestamp() > access_token_exp_threshold:
                if self._multiprocessing_safe and not already_updated_from_cache:
                    # ONLY ONE PROCESS / THREAD CAN GET A NEW TOKEN AT THE SAME TIME! Update from cache then revalidate!
                    # Only using the multiprocessing cache here prevents added latency checking cross process values
                    #  except when the token has expired, which should only be once every 30 minutes. Better than making
                    #  state a full MP dict.
                    with self._multiprocessing_lock:
                        self.state.update(dict(self._cached_state))
                        self.validate_token(already_updated_from_cache=True)
                else:
                    print("Grabbing new access token...")
                    self.grab_access_token()

            return True

        else:
            
            pprint.pprint(
                {
                    "credential_path": str(self.credentials_path),
                    "message": "The credential file does not contain expiration times for your tokens, please go through the oAuth process."
                }
            )

            return False

    def _silent_sso(self) -> bool:
        """
        Overview:
        ----
        Attempt a silent authentication, by checking whether current
        access token is valid and/or attempting to refresh it. Returns
        True if we have successfully stored a valid access token.
        ### Returns:
        ----
        {bool} -- Specifies whether it was successful or not.
        """

        if self.validate_token():
            return True
        else:
            return False

    def _token_save(self, token_dict: dict, includes_refresh: bool = False) -> dict:
        """Parses the token and saves it.
        
        Overview:
        ----
        Parses an access token from the response of a POST request and saves it
        in the state dictionary for future use. Additionally, it will store the
        expiration time and the refresh token.
        ### Arguments:
        ----
        token_dict {dict} -- A response object recieved from the `grab_refresh_token` or
            `grab_access_token` methods.
        
        ### Returns:
        ----
        {dict} -- A token dictionary with the new added values.
        """

        # store token expiration time
        access_token_expire = time.time() + int(token_dict['expires_in'])
        acc_timestamp = datetime.datetime.fromtimestamp(access_token_expire)
        acc_timestamp = acc_timestamp.isoformat()

        # Save to the State.
        self.state['access_token'] = token_dict['access_token']
        self.state['access_token_expires_at'] = access_token_expire
        self.state['access_token_expires_at_date'] = acc_timestamp

        if includes_refresh:

            refresh_token_expire = time.time() + int(token_dict['refresh_token_expires_in'])
            ref_timestamp = datetime.datetime.fromtimestamp(refresh_token_expire)
            ref_timestamp = ref_timestamp.isoformat()

            # Save to the State.
            self.state['refresh_token'] = token_dict['refresh_token']
            self.state['refresh_token_expires_at'] = refresh_token_expire
            self.state['refresh_token_expires_at_date'] = ref_timestamp

        self.state['logged_in'] = True
        if self._multiprocessing_safe:
            self._cached_state.update(self.state)
        self._state_manager('save')

        return self.state

    def _make_request(self, method: str, endpoint: str, mode: str = None, params: dict = None, data: dict = None, json:dict = None, 
                        order_details: bool = False) -> Any:
        """Handles all the requests in the library.
        A central function used to handle all the requests made in the library,
        this function handles building the URL, defining Content-Type, passing
        through payloads, and handling any errors that may arise during the request.
        ### Arguments:
        ----
        method: The Request method, can be one of the
            following: ['get','post','put','delete','patch']
        
        endpoint: The API URL endpoint, example is 'quotes'
        mode: The content-type mode, can be one of the
            following: ['form','json']
        
        params: The URL params for the request.
        
        data: A data payload for a request.
        json: A json data payload for a request
        ### Returns:
        ----
        A Dictionary object containing the JSON values.            
        """

        url = self._api_endpoint(endpoint=endpoint)

        # Make sure the token is valid if it's not a Token API call.
        # self.validate_token()
        headers = self._headers(mode=mode)

        # Define a new session.
        request_session = requests.Session()
        request_session.verify = True

        # Define a new request.
        request_request = requests.Request(
            method=method.upper(),
            headers=headers,
            url=url,
            params=params,
            data=data,
            json=json
        ).prepare()
        
        # Send the request.
        response: requests.Response = request_session.send(request=request_request)

        request_session.close()

        # grab the status code
        status_code = response.status_code

        # grab the response headers.
        response_headers = response.headers

        # Grab the order id, if it exists.
        if 'Location' in response_headers:            
            order_id = response_headers['Location'].split('orders/')[1]
        else:
            order_id = ''

        # If it's okay and we need details, then add them.
        if response.ok and order_details:

            response_dict = {
                'order_id':order_id,
                'headers':response_headers,
                'content':response.content,
                'status_code':status_code,
                'request_body':response.request.body,
                'request_method':response.request.method
            }

            return response_dict

        # If it's okay and no details.
        elif response.ok:
            return response.json()

        else:

            if response.status_code == 400:
                raise NotNulError(message=response.text)
            elif response.status_code == 401:
                try:
                    self.grab_access_token()
                except:
                    raise TknExpError(message=response.text)
            elif response.status_code == 403:
                raise ForbidError(message=response.text)
            elif response.status_code == 404:
                raise NotFndError(message=response.text)
            elif response.status_code == 429:
                raise ExdLmtError(message=response.text)
            elif response.status_code == 500 or response.status_code == 503:
                raise ServerError(message=response.text)
            elif response.status_code > 400:
                raise GeneralError(message=response.text)

    def _validate_arguments(self, endpoint: str, parameter_name: str, parameter_argument: List[str]) -> bool:
        """Validates arguments for an API call.
        This will validate an argument for the specified endpoint and raise an error if the argument
        is not valid. Can take both a list of arguments or a single argument.
        ### Arguments:
        ----
        endpoint {str} -- This is the endpoint name, and should line up 
            exactly with the TD Ameritrade Client library.
        parameter_name {str} -- An endpoint can have a parameter that needs 
            to be passed through, this represents the name 
            of that parameter.
        parameter_argument {List[str]} -- The arguments being validated for the 
            particular parameter name. This can either be a single value or a list 
            of values.
        ### Returns:
        ----
        {bool} --- If all arguments are valid then `True`, `False` if any are invalid.
        
        Raises:
        ----
        ValueError()
        ### Usage:
        ----
            >>> api_endpoint = 'get_market_hours'
            >>> para_name = 'markets'
            >>> para_args = ['FOREX', 'EQUITY']
            >>> self.validate_arguments(
                endpoint = api_endpoint, 
                parameter_name = para_name, 
                parameter_argument = para_args
            )
        """

        message = '\nThe argument is not valid, please choose a valid argument: {}\n'

        # Grab the parameters, and the possible arguments.
        parameters = ENDPOINT_ARGUMENTS[endpoint]
        arguments = parameters[parameter_name]

        if isinstance(parameter_argument,str):
            parameter_argument = [parameter_argument]

        # See if any of the arguments aren't in the possible values.
        validation_result = [argument in arguments for argument in parameter_argument]

        # if any of the results are FALSE then raise an error.
        if False in validation_result:
            raise ValueError(message.format(' ,'.join(arguments)))
        else:
            return True

    def _prepare_arguments_list(self, parameter_list: List) -> str:
        """Preps an argument list for an API Call.
        Some endpoints can take multiple values for a parameter, this
        method takes that list and creates a valid string that can be 
        used in an API request. The list can have either one index or
        multiple indexes.
        ### Arguments:
        ----
        parameter_list: A list of paramater values 
            assigned to an argument.
        ### Usage:
        ----
            >>> td_client._prepare_arguments_list(
                    parameter_list=['MSFT', 'SQ']
                )
        """

        return ','.join(parameter_list)

    def get_quotes(self, instruments: List) -> Dict:
        """Grabs real-time quotes for an instrument.
        Serves as the mechanism to make a request to the Get Quote and Get Quotes Endpoint.
        If one item is provided a Get Quote request will be made and if more than one item
        is provided then a Get Quotes request will be made.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/quotes/apis
        ### Arguments:
        ----
        instruments: A list of different financial instruments.
        ### Usage:
        ----
            >>> td_client.get_quotes(instruments=['MSFT'])
            >>> td_client.get_quotes(instruments=['MSFT','SQ'])
        """
        # because we have a list argument, prep it for the request.
        instruments = self._prepare_arguments_list(
            parameter_list=instruments
        )

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'symbol': instruments
        }

        # define the endpoint
        endpoint = 'marketdata/quotes'

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_price_history(self, symbol: str, period_type:str = None, period: str = None, start_date:str = None, end_date:str = None,
                          frequency_type: str = None, frequency: str = None, extended_hours: bool = True) -> Dict:
        """Gets historical candle data for a financial instrument.
        
        ### Documentation:
        ----
        https://developer.tdameritrade.com/price-history/apis
        ### Arguments:
        ----
        symbol: The ticker symbol to request data for. 
        period_type: The type of period to show. 
            Valid values are day, month, year, or 
            ytd (year to date). Default is day.
        period: The number of periods to show.
        
        start_date: Start date as milliseconds
            since epoch.
        end_date: End date as milliseconds
            since epoch.
        frequency_type: The type of frequency with 
            which a new candle is formed.
        frequency: The number of the frequency type 
            to be included in each candle.
        extended_hours: True to return extended hours 
            data, false for regular market hours only.
            Default is true
        """

        # Fail early, can't have a period with start and end date specified.
        if (start_date and end_date and period):
            raise ValueError('Cannot have Period with start date and end date')
        
        # Check only if you don't have a date and do have a period.
        elif (not start_date and not end_date and period):

            # Attempt to grab the key, if it fails we know there is an error.
            # check if the period is valid.
            if int(period) in VALID_CHART_VALUES[frequency_type][period_type]:
                True
            else:
                raise IndexError('Invalid Period.')

            if frequency_type == 'minute' and int(frequency) not in [1, 5, 10, 15, 30]:
                raise ValueError('Invalid Minute Frequency, must be 1,5,10,15,30')

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'startDate': start_date,
            'endDate': end_date,
            'frequency': frequency,
            'frequencyType': frequency_type,
        }

        # define the endpoint
        endpoint = 'marketdata/{}/pricehistory'.format(symbol)

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)
    
    def get_price_for_current_day(self, symbol: str) -> Dict:
        url = "https://api.tdameritrade.com/v1/marketdata/SPY/pricehistory?apikey=GPH5HXCYICGCYMQWFGNZAGK8EQJIUX5N&frequencyType=minute&frequency=1&startDate=1639837800000&endDate=1640110857602"
        x = requests.get(url)
        return x.json()

    def search_instruments(self, symbol: str, projection: str = None) -> Dict:
        """ Search or retrieve instrument data, including fundamental data.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/instruments/apis/get/instruments
        ### Arguments:
        ----
        symbol: The symbol of the financial instrument you would 
            like to search.
        
        projection: The type of request, default is "symbol-search". 
            The type of request include the following:
            1. symbol-search
                Retrieve instrument data of a specific symbol or cusip
            2. symbol-regex
                Retrieve instrument data for all symbols matching regex. 
                Example: symbol=XYZ.* will return all symbols beginning with XYZ
            3. desc-search
                Retrieve instrument data for instruments whose description contains 
                the word supplied. Example: symbol=FakeCompany will return all 
                instruments with FakeCompany in the description
            4. desc-regex
                Search description with full regex support. Example: symbol=XYZ.[A-C] 
                returns all instruments whose descriptions contain a word beginning 
                with XYZ followed by a character A through C
            5. fundamental
                Returns fundamental data for a single instrument specified by exact symbol.
        ### Usage:
        ----
            >>> td_client.search_instrument(
                    symbol='XYZ',
                    projection='symbol-search'
                )
            >>> td_client.search_instrument(
                    symbol='XYZ.*',
                    projection='symbol-regex'
                )
            >>> td_client.search_instrument(
                    symbol='FakeCompany',
                    projection='desc-search'
                )
            >>> td_client.search_instrument(
                    symbol='XYZ.[A-C]',
                    projection='desc-regex'
                )
            >>> td_client.search_instrument(
                    symbol='XYZ.[A-C]',
                    projection='fundamental'
                )
        """

        # validate argument
        self._validate_arguments(
            endpoint='search_instruments',
            parameter_name='projection', 
            parameter_argument=projection
        )

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'symbol': symbol,
            'projection': projection
        }

        # define the endpoint
        endpoint = 'instruments'

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_instruments(self, cusip: str) -> Dict:
        """Searches an Instrument.
        
        Get an instrument by CUSIP (Committee on Uniform Securities Identification Procedures) code.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/instruments/apis/get/instruments/%7Bcusip%7D
        ### Arguments:
        ----
        cusip: The CUSIP code of a given financial instrument.
        
        ### Usage:
        ----
            >>> td_client.get_instruments(
                cusip='SomeCUSIPNumber'
            )
        """

        # build the params dictionary
        params = {
            'apikey': self.client_id
        }

        # define the endpoint
        endpoint = 'instruments/{cusip}'.format(cusip=cusip)

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_market_hours(self, markets: List[str], date: str) -> Dict:
        """Returns the hours for a specific market.
        Serves as the mechanism to make a request to the "Get Hours for Multiple Markets" and 
        "Get Hours for Single Markets" Endpoint. If one market is provided a "Get Hours for Single Markets" 
        request will be made and if more than one item is provided then a "Get Hours for Multiple Markets" 
        request will be made.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/market-hours/apis
        
        ### Arguments:
        ----
        markets: The markets for which you're requesting market hours, 
            comma-separated. Valid markets are:
            EQUITY, OPTION, FUTURE, BOND, or FOREX.
        date: The date you wish to recieve market hours for. 
            Valid ISO-8601 formats are: yyyy-MM-dd and yyyy-MM-dd'T'HH:mm:ssz
        ### Usage:
        ----
            >>> td_client.get_market_hours(markets=['EQUITY'], date='2019-10-19')
            >>> td_client.get_market_hours(markets=['EQUITY','FOREX'], date='2019-10-19')
        """

        # validate argument
        self._validate_arguments(
            endpoint='get_market_hours',
            parameter_name='markets', 
            parameter_argument=markets
        )

        # because we have a list argument, prep it for the request.
        markets = self._prepare_arguments_list(parameter_list=markets)

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'markets': markets,
            'date': date
        }

        # define the endpoint
        endpoint = 'marketdata/hours'

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_movers(self, market: str, direction: str, change: str) -> Dict:
        """Gets Active movers for a specific Index.
        
        Top 10 (up or down) movers by value or percent for a particular market.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/movers/apis/get/marketdata
        ### Arguments:
        ----
        market: The index symbol to get movers for. 
            Can be $DJI, $COMPX, or $SPX.X.
        direction: To return movers with the specified 
            directions of up or down. Valid values are `up`
            or `down`
        change: To return movers with the specified change 
            types of percent or value. Valid values are `percent`
            or `value`.   
        ### Usage:
        ----
            >>> td_client.get_movers(
                    market='$DJI',
                    direction='up',
                    change='value'
                )
            >>> td_client.get_movers(
                    market='$COMPX',
                    direction='down',
                    change='percent'
                )
        """

        # grabs a dictionary representation of our arguments and their inputs.
        local_args = locals()

        # we don't need the 'self' key
        del local_args['self']

        # validate arguments, before making request.
        for key, value in local_args.items():
            self._validate_arguments(
                endpoint='get_movers', 
                parameter_name=key, 
                parameter_argument=value
            )

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'direction': direction,
            'change': change
        }

        # define the endpoint
        endpoint = 'marketdata/{market_id}/movers'.format(market_id=market)

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_options_chain(self, option_chain: Union[Dict, OptionChain]) -> Dict:
        """Returns Option Chain Data and Quotes.
        Get option chain for an optionable Symbol using one of two methods. Either,
        use the OptionChain object which is a built-in object that allows for easy creation
        of the POST request. Otherwise, can pass through a dictionary of all the 
        arguments needed.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/option-chains/apis/get/marketdata/chains
        ### Arguments:
        ----
        option_chain: Represents a dicitonary containing values to
            query.
        ### Usage:
        ----
            >>> td_client.get_options_chain(
                option_chain={'key1':'value1'}
            )
        """

        # First check if it's an `OptionChain` object.
        if isinstance(option_chain, OptionChain):

            # If it is, then grab the params.
            params = option_chain.query_parameters
        
        else:

            # Otherwise just take the raw dictionary.
            params = option_chain

        # define the endpoint
        endpoint = 'marketdata/chains'

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    """
    -----------------------------------------------------------
    -----------------------------------------------------------
    
        THIS BEGINS THE ACCOUNTS ENDPOINTS PORTION.
    -----------------------------------------------------------
    -----------------------------------------------------------
    """

    def get_accounts(self, account: str = 'all', fields: List[str] = None) -> Dict:
        """Queries accounts for a user.
        Serves as the mechanism to make a request to the "Get Accounts" and "Get Account" Endpoint. 
        If one account is provided a "Get Account" request will be made and if more than one account 
        is provided then a "Get Accounts" request will be made.
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/account-access/apis
        ### Arguments:
        ----
        account {str} -- The account number you wish to recieve data on. Default value is 'all'
                which will return all accounts of the user.
        fields {List[str]} -- Balances displayed by default, additional fields can be added here by 
                adding positions or orders.
        ### Usage:
        ----
            >>> td_client.get_accounts(
                    account='all',
                    fields=['orders']
                )
            >>> td_client.get_accounts(
                    account='MyAccountNumber',
                    fields=['orders','positions']
                )
        """

        # because we have a list argument, prep it for the request.
        if fields:
            fields = self._prepare_arguments_list(parameter_list=fields)

        # build the params dictionary
        params = {
            'apikey': self.client_id,
            'fields': fields
        }

        # if all use '/accounts' else pass through the account number.
        if account == 'all':
            endpoint = 'accounts'
        else:
            endpoint = 'accounts/{}'.format(account)

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)


    def get_transactions(self, account: str = None, transaction_type: str = None, symbol: str = None,
                         start_date: str = None, end_date: str = None, transaction_id: str= None) -> Dict:
        """Queries the transactions for an account.
    
        Serves as the mechanism to make a request to the "Get Transactions" and "Get Transaction" Endpoint. 
        If one `transaction_id` is provided a "Get Transaction" request will be made and if it is not provided
        then a "Get Transactions" request will be made.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/transaction-history/apis
        ### Arguments:
        ----
        account {str} -- The account number you wish to recieve
        transactions for.
        transaction_type: The type of transaction. Only 
            transactions with the specified type will be returned. 
            Valid values are the following:
                1. ALL
                2. TRADE
                3. BUY_ONLY
                4. SELL_ONLY
                5. CASH_IN_OR_CASH_OUT
                6. CHECKING
                7. DIVIDEND
                8. INTEREST
                9. OTHER
                10. ADVISOR_FEES
        symbol The symbol in the specified transaction. Only transactions
            with the specified symbol will be returned.
        start_date: Only transactions after the Start Date will be returned. 
            Note: The maximum date range is one year. Valid ISO-8601 
            formats are: yyyy-MM-dd.
        end_date: Only transactions before the End Date will be returned. 
            Note: The maximum date range is one year. Valid ISO-8601 
            formats are: yyyy-MM-dd.
        transaction_id: The transaction ID you wish to search. If this is 
            specifed a "Get Transaction" request is made. Should only be
            used if you wish to return one transaction.
        ### Usage:
        ----
            >>> td_client.get_transactions(account = 'MyAccountNumber', transaction_type = 'ALL', start_date = '2019-01-31', end_date = '2019-04-28')
            >>> td_client.get_transactions(account = 'MyAccountNumber', transaction_type = 'ALL', start_date = '2019-01-31')
            >>> td_client.get_transactions(account = 'MyAccountNumber', transaction_type = 'TRADE')
            >>> td_client.get_transactions(transaction_id = 'MyTransactionID')
        """

        # default to a "Get Transaction" Request if anything else is passed through along with the transaction_id.
        if transaction_id != None:
            account = None
            transaction_type = None,
            start_date = None,
            end_date = None

        # if the request type they made isn't valid print an error and return nothing.
        else:

            if transaction_type not in ['ALL', 'TRADE', 'BUY_ONLY', 'SELL_ONLY', 'CASH_IN_OR_CASH_OUT', 'CHECKING', 'DIVIDEND', 'INTEREST', 'OTHER', 'ADVISOR_FEES']:
                print('The type of transaction type you specified is not valid.')
                raise ValueError('Bad Input')

        # if transaction_id is not none, it means we need to make a request to the get_transaction endpoint.
        if transaction_id:

            # define the endpoint
            endpoint = 'accounts/{}/transactions/{}'.format(account, transaction_id)

            # return the response of the get request.
            return self._make_request(method='get', endpoint=endpoint)

        # if it isn't then we need to make a request to the get_transactions endpoint.
        else:

            # build the params dictionary
            params = {
                'type': transaction_type,
                'symbol': symbol,
                'startDate': start_date,
                'endDate': end_date
            }

            if account is None and self.account_number:
                account = self.account_number

            # define the endpoint
            endpoint = 'accounts/{}/transactions'.format(account)

            # return the response of the get request.
            return self._make_request(method='get', endpoint=endpoint, params=params)

    """
    -----------------------------------------------------------
    -----------------------------------------------------------
    
        THIS BEGINS THE USER INFOS & PREFERENCES ENDPOINTS PORTION.
    -----------------------------------------------------------
    -----------------------------------------------------------
    """

    def get_preferences(self, account: str) -> Dict:
        """Get's User Preferences for a specific account.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/user-principal/apis/get/accounts/%7BaccountId%7D/preferences-0
        ### Arguments:
        ----
        account {str} -- The account number you wish to 
            recieve preference data for.
        ### Usage:
        ----
            >>> td_client.get_preferences(account='MyAccountNumber')
        
        ### Returns:
        ----
            Perferences dictionary
        """

        # define the endpoint
        endpoint = 'accounts/{}/preferences'.format(account)

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint)

    def get_streamer_subscription_keys(self, accounts: List[str]) -> Dict:
        """SubscriptionKey for provided accounts or default accounts.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/user-principal/apis/get/userprincipals/streamersubscriptionkeys-0
        ### Arguments:
        ----
        account:A list of account numbers you wish to recieve a 
            streamer key for.
        ### Usage:
        ----
            >>> td_client.get_streamer_subscription_keys(account=['MyAccountNumber'])
            >>> td_client.get_streamer_subscription_keys(account=['MyAccountNumber1', 'MyAccountNumber2'])
        """


        # because we have a list argument, prep it for the request.
        accounts = self._prepare_arguments_list(parameter_list=accounts)

        # define the endpoint
        endpoint = 'userprincipals/streamersubscriptionkeys'

        # build the params dictionary
        params = {
            'accountIds': accounts
        }

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_user_principals(self, fields: List[str]) -> Dict:
        """Returns User Principal details.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/user-principal/apis/get/userprincipals-0
        ### Arguments:
        ----
        fields: A comma separated String which allows one to specify additional fields to return. None of 
            these fields are returned by default. Possible values in this String can be:
                1. streamerSubscriptionKeys
                2. streamerConnectionInfo
                3. preferences
                4. surrogateIds
        ### Usage:
        ----
            >>> td_client.get_user_principals(fields=['preferences'])
            >>> td_client.get_user_principals(fields=['preferences','streamerConnectionInfo'])
        """

        # validate arguments
        self._validate_arguments(
            endpoint='get_user_principals',
            parameter_name='fields', 
            parameter_argument=fields
        )

        # because we have a list argument, prep it for the request.
        fields = self._prepare_arguments_list(parameter_list=fields)

        # define the endpoint
        endpoint = 'userprincipals'

        # build the params dictionary
        params = {
            'fields': fields
        }

        # return the response of the get request.
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def update_preferences(self, account: str, data_payload: Dict) -> Dict:
        """Updates the User's Preferences.
        Overview:
        ----
        Update preferences for a specific account. Please note that the 
        `directOptionsRouting` and `directEquityRouting` values cannot be modified
        via this operation.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/user-principal/apis/put/accounts/%7BaccountId%7D/preferences-0
        ### Arguments:
        ----        
        account: The account number you wish to update preferences for.
        data_payload: A dictionary that provides all the keys you wish to update. 
            It must contain the following keys to be valid.
                1. expressTrading
                2. directOptionsRouting
                3. directEquityRouting
                4. defaultEquityOrderLegInstruction
                5. defaultEquityOrderType
                6. defaultEquityOrderPriceLinkType
                7. defaultEquityOrderDuration
                8. defaultEquityOrderMarketSession
                9. defaultEquityQuantity
                10. mutualFundTaxLotMethod
                11. optionTaxLotMethod
                12. equityTaxLotMethod
                13. defaultAdvancedToolLaunch
                14. authTokenTimeout
        
        ### Usage:
        ----
            >>> td_client.update_preferences(account='MyAccountNumer', dataPayload=<Dictionary>)
        """

        # define the endpoint
        endpoint = 'accounts/{}/preferences'.format(account)

        # make the request
        return self._make_request(method='put', endpoint=endpoint, mode='json', data=data_payload)

    """
    -----------------------------------------------------------
    -----------------------------------------------------------
    
        THIS BEGINS THE WATCHLISTS ENDPOINTS PORTION.
    -----------------------------------------------------------
    -----------------------------------------------------------
    """

    def create_watchlist(self, account: str, name: str, watchlistItems=None) -> Dict:
        """Creates a new watchlist.
        Create watchlist for specific account. This method does not verify that the 
        symbol or asset type are valid.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/watchlist/apis/post/accounts/%7BaccountId%7D/watchlists-0
        ### Arguments:
        ----        
        account: The account number you wish to create the watchlist for.
        name: The name you want to give your watchlist.
        watchlistItems: A list of WatchListItems object.
        ### Usage:
        ----
            >>> td_client.create_watchlist(
                account = 'MyAccountNumber', 
                name = 'MyWatchlistName', 
                watchlistItems = {'key':'value'}
            )
        """

        # define the endpoint
        endpoint = 'accounts/{}/watchlists'.format(account)

        # define the payload
        payload = {
            "name": name,
            "watchlistItems": watchlistItems
        }

        # make the request
        return self._make_request(method='put', endpoint=endpoint, mode='json', data=payload)

    def get_watchlist_accounts(self, account: str = 'all') -> Dict:
        """Gets watchlist, by account number.
        Serves as the mechanism to make a request to the "Get Watchlist for Single Account" and 
        "Get Watchlist for Multiple Accounts" Endpoint. If one account is provided a 
        "Get Watchlist for Single Account" request will be made and if 'all' is provided then a 
        "Get Watchlist for Multiple Accounts" request will be made.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/watchlist/apis
        ### Arguments:
        ----
        account: The account number you wish to pull watchlists from. Default value is 'all'
        ### Usage:
        ----
            >>> td_client.get_watchlist_accounts(account='all')
            >>> td_client.get_watchlist_accounts(account='MyAccount1')
        """

        # define the endpoint
        if account == 'all':
            endpoint = 'accounts/watchlists'
        else:
            endpoint = 'accounts/{}/watchlists'.format(account)

        # make the request
        return self._make_request(method='get', endpoint=endpoint)

    def get_watchlist(self, account: str, watchlist_id: str) -> Dict:
        """Queries a watchlist.
        
        Returns a specific watchlist for a specific account designated by the
        watchlist ID.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/watchlist/apis/get/accounts/%7BaccountId%7D/watchlists/%7BwatchlistId%7D-0
        ### Arguments:
        ----
        account:The account number you wish to pull watchlists from.
        watchlist_id: The ID of the watchlist you wish to return.
        ### Usage:
        ----
            >>> td_client.get_watchlist(
                account='MyAccount1',
                watchlist_id='MyWatchlistId'
            )
        """

        # define the endpoint
        endpoint = 'accounts/{}/watchlists/{}'.format(account, watchlist_id)

        # make the request
        return self._make_request(method='get', endpoint=endpoint)

    def delete_watchlist(self, account: str, watchlist_id: str) -> Dict:
        """Deletes an existing watchlist
        Deletes a specific watchlist for a specific account.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/watchlist/apis/delete/accounts/%7BaccountId%7D/watchlists/%7BwatchlistId%7D-0
        ### Arguments:
        ----
        account: The account number you wish to delete the watchlist from.
        watchlist_id: The ID of the watchlist you wish to delete.
        ### Usage:
        ----
            >>> td_client.delete_watchlist(
                account='MyAccount1',
                watchlist_id='MyWatchlistId'
            )
        """


        # define the endpoint
        endpoint = 'accounts/{}/watchlists/{}'.format(account, watchlist_id)

        # make the request
        return self._make_request(method='delete', endpoint=endpoint)

    def update_watchlist(self, account: str, watchlist_id: str, name: str, watchlistItems: Dict) -> Dict:
        """Updates an Exisitng watchlist.
        Partially update watchlist for a specific account: change watchlist name, add to the beginning/end of a 
        watchlist, update or delete items in a watchlist. This method does not verify that the symbol or asset 
        type are valid.
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/watchlist/apis/patch/accounts/%7BaccountId%7D/watchlists/%7BwatchlistId%7D-0
        ### Arguments:
        ----
        account: The account number that contains the watchlist you wish to update.
        watchlist_id: The ID of the watchlist you wish to update.
        watchlistItems: A list of the original watchlist items you wish to update and their modified keys.
         
        ### Usage:
        ----
            >>> td_client.update_watchlist(
                account = 'MyAccountNumber', 
                watchlist_id = 'WatchListID', 
                watchlistItems = [WatchListItem1, WatchListItem2]
            )
        """

        # define the payload
        payload = {
            "name": name,
            "watchlistItems": watchlistItems
        }

        # define the endpoint
        endpoint = 'accounts/{}/watchlists/{}'.format(account, watchlist_id)

        # make the request
        return self._make_request(method='patch', endpoint=endpoint, data=payload)

    def replace_watchlist(self, account: str, watchlist_id_new: dict, watchlist_id_old: dict, name_new: str, watchlistItems_new: dict) -> Dict:
        """Replaces an existing watchlist.
            
        Replace watchlist for a specific account. This method does not verify that 
        the symbol or asset type are valid.
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/watchlist/apis/put/accounts/%7BaccountId%7D/watchlists/%7BwatchlistId%7D-0
        ### Arguments:
        ----
        account: The account number that contains the watchlist you wish to replace.
        watchlist_id_new: The ID of the watchlist you wish to replace with the old one.
        watchlist_id_old: The ID of the watchlist you wish to replace.
        name_new The name: of the new watchlist.
        watchlistItems_New: The new watchlist items you wish to add to the watchlist.
         
        ### Usage:
        ----
            >>> td_client.replace_watchlist(
                account = 'MyAccountNumber', 
                watchlist_id_new = 'WatchListIDNew', 
                watchlist_id_old = 'WatchListIDOld', 
                name_new = 'MyNewName', 
                watchlistItems_new = {key:value}
            )
        """

        # define the payload
        payload = {
            "name": name_new,
            "watchlistId": watchlist_id_new,
            "watchlistItems": watchlistItems_new
        }

        # define the endpoint
        endpoint = 'accounts/{}/watchlists/{}'.format(account, watchlist_id_old)

        # make the request
        return self._make_request(method='put', endpoint=endpoint, mode='json', data=payload)

    """
    -----------------------------------------------------------
    -----------------------------------------------------------
        THIS BEGINS THE ORDERS ENDPOINTS PORTION.
    -----------------------------------------------------------
    -----------------------------------------------------------
    """

    def get_orders_path(self, account: str, max_results: int = None, from_entered_time: 
                            str = None, to_entered_time: str = None, status: str = None) -> Dict:
        """Returns the orders for a specific account.
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/account-access/apis/get/accounts/%7BaccountId%7D/orders-0
        ### Arguments:
        ----
        account: The account number that you want to query for orders.
        max_results: The maximum number of orders to retrieve.
        from_entered_time: Specifies that no orders entered before this time should be returned. Valid ISO-8601 formats are:
            yyyy-MM-dd and yyyy-MM-dd'T'HH:mm:ssz Date must be within 60 days from today's date. 'to_entered_time' 
            must also be set.
        to_entered_time: Specifies that no orders entered after this time should be returned.Valid ISO-8601 formats are:
            yyyy-MM-dd and yyyy-MM-dd'T'HH:mm:ssz. 'from_entered_time' must also be set.
        status: Specifies that only orders of this status should be returned. 
            Possible Values are:
            >>> 1. AWAITING_PARENT_ORDER
                2. AWAITING_CONDITION
                3. AWAITING_MANUAL_REVIEW
                4. ACCEPTED
                5. AWAITING_UR_NOT
                6. PENDING_ACTIVATION
                7. QUEDED
                8. WORKING
                9. REJECTED
                10. PENDING_CANCEL
                11. CANCELED
                12. PENDING_REPLACE
                13. REPLACED
                14. FILLED
                15. EXPIRED
        ### Usage:
        ----
            >>> td_client.get_orders_path(
                account='MyAccountID',
                max_results=6,
                from_entered_time='2019-10-01',
                to_entered_time='2019-10-10',
                status='FILLED'
            )
            
            >>> td_client.get_orders_path(
                account='MyAccountID',
                max_results=6,
                status='EXPIRED'
            )
            
            >>> td_client.get_orders_path(
                account='MyAccountID',
                status='REJECTED'
            )
            
            >>> td_client.get_orders_query(
                account = 'MyAccountID'
            )
        """

        # define the payload
        params = {
            "maxResults": max_results, 
            "fromEnteredTime": from_entered_time,
            "toEnteredTime": to_entered_time,
            "status": status
        }

        # define the endpoint
        endpoint = 'accounts/{}/orders'.format(account)

        # make the request
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_orders_query(self, account: str = None, max_results: int = None, from_entered_time: str = None, 
                            to_entered_time: str = None, status: str = None) -> Dict:
        """Get's all the orders for an account.
        All orders for a specific account or, if account ID isn't specified, orders will be returned for all linked accounts
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/get/orders-0
        ### Arguments:
        ----
        account: The account number that you want to query for orders, or if none provided will query all.
        max_results: The maximum number of orders to retrieve.
        from_entered_time: Specifies that no orders entered before this time should be returned. Valid ISO-8601 formats are:
            yyyy-MM-dd and yyyy-MM-dd'T'HH:mm:ssz Date must be within 60 days from today's date. 'to_entered_time' 
            must also be set.
        to_entered_time: Specifies that no orders entered after this time should be returned.Valid ISO-8601 formats are:
            yyyy-MM-dd and yyyy-MM-dd'T'HH:mm:ssz. 'from_entered_time' must also be set.
        status: Specifies that only orders of this status should be returned.
            Possible Values are:
            >>> 1. AWAITING_PARENT_ORDER
            >>> 2. AWAITING_CONDITION
            >>> 3. AWAITING_MANUAL_REVIEW
            >>> 4. ACCEPTED
            >>> 5. AWAITING_UR_NOT
            >>> 6. PENDING_ACTIVATION
            >>> 7. QUEDED
            >>> 8. WORKING
            >>> 9. REJECTED
            >>> 10. PENDING_CANCEL
            >>> 11. CANCELED
            >>> 12. PENDING_REPLACE
            >>> 13. REPLACED
            >>> 14. FILLED
            >>> 15. EXPIRED
                  
        ### Usage:
        ----
            >>> td_client.get_orders_query(
                account='MyAccountID',
                max_results=6,
                from_entered_time='2019-10-01',
                to_entered_time='2019-10-10',
                status='FILLED'
            )
            >>> td_client.get_orders_query(
                account='MyAccountID',
                max_results=6,
                status='EXPIRED'
            )
            >>> td_client.get_orders_query(
                account='MyAccountID',
                status='REJECTED'
            )
            >>> td_client.get_orders_query()
        """

        # define the payload
        params = {
            "accountId": account,
            "maxResults": max_results,
            "fromEnteredTime": from_entered_time,
            "toEnteredTime": to_entered_time,
            "status": status
        }

        # define the endpoint
        endpoint = 'orders'

        # make the request
        return self._make_request(method='get', endpoint=endpoint, params=params)

    def get_orders(self, account: str, order_id: str = None) -> Dict:
        """Gets the orders for an account
        Returns all orders for a specific account or, if account ID 
        isn't specified, orders will be returned for all linked
        accounts.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/get/orders-0
        
        ### Arguments:
        ----
        account {str} -- The account number that you want to query orders for.
        
        Keyword ### Arguments:
        ----
        order_id {str} -- The ID of the order you want to delete. (default: {None})
        
        ### Usage:
        ----
            >>> td_client.get_order(account='MyAccountID', order_id='MyOrderID')
        
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """
        

        # define the endpoint
        if order_id:
            endpoint = 'accounts/{}/orders/{}'.format(account, order_id)
        else:
            endpoint = 'accounts/{}/orders'.format(account)

        # make the request
        return self._make_request(method='get', endpoint=endpoint)

    def cancel_order(self, account: str, order_id: str) -> Dict:
        """Cancel a specific order for a specific account.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/delete/accounts/%7BaccountId%7D/orders/%7BorderId%7D-0
        ### Arguments:
        ----
        account {str} -- The account number that the order was made for.
        order_id {str} -- The ID of the order you want to delete.
        ### Usage:
        ----
            >>> td_client.cancel_order(account='MyAccountID', order_id='MyOrderID')
        
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """

        # define the endpoint
        endpoint = 'accounts/{}/orders/{}'.format(account, order_id)

        # delete the request
        return self._make_request(method='delete', endpoint=endpoint, order_details=True)


    def place_order(self, account: str, order: dict) -> dict:
        """Places an order for a specific account.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/delete/accounts/%7BaccountId%7D/orders/%7BorderId%7D-0
        ### Arguments:
        ----
        account {str} -- The account number that you want to place the order for.
        order {dict} -- The order payload.
        ### Usage:
        ----
            >>> td_client.place_order(account='MyAccountID', order={'orderKey':'OrderValue'})
        
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """

        # check to see if it's an order object.
        if isinstance(order, Order):
            order = order._grab_order()
        else:
            order = order

        # make the request
        endpoint = 'accounts/{}/orders'.format(account)
        return self._make_request(method='post', endpoint=endpoint, mode='json', json=order, order_details=True)
    
    def modify_order(self, account: str, order: dict, order_id: str) -> dict:
        """Modifies an exisiting order.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/delete/accounts/%7BaccountId%7D/orders/%7BorderId%7D-0
        ### Arguments:
        ----
        account {str} -- The account number that the order was place for.
        order {dict} -- The new order payload.
        order_id {str} -- The ID of the exisitng order.
        ### Usage:
        ----
            >>> td_client.place_order(account='MyAccountID', order={'orderKey':'OrderValue'})
        
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """

        # Check if it's an order.
        if isinstance(order, Order):
            order = order._grab_order()
        else:
            order = order

        # make the request
        endpoint = 'accounts/{account_id}/orders/{order_id}'.format(
            account_id=account,
            order_id=order_id
        )

        return self._make_request(
            method='put',
            endpoint=endpoint,
            mode='json',
            json=order,
            order_details=True
        )

    def get_saved_order(self, account: str, saved_order_id: str = None) -> Dict:
        """Grabs a saved order.
        Grabs all the saved orders for a specific account or, if account 
        ID isn't specified, orders will be returned for all linked accounts
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/account-access/apis/get/orders-0
        ### Arguments:
        ----
        account {str} -- The account number that you want to place the order for.
        saved_order_id {str} --  The saved order id.
        
        ### Usage:
        ----
            >>> td_client.get_order(account='MyAccountID', saved_order_id='MyOrderID')
        ### Returns:
        ----
        {dict} -- A response dicitonary.   
        """

        # define the endpoint
        endpoint = 'accounts/{}/savedorders/{}'.format(account, saved_order_id)
        return self._make_request(method='get', endpoint=endpoint)

    def cancel_saved_order(self, account: str, saved_order_id: str) -> Dict:
        """Cancel a saved order 
        
        Using a saved order ID and account number, will delete the order from
        the specified account.
        ### Documentation:
        ---- 
        https://developer.tdameritrade.com/account-access/apis/delete/accounts/%7BaccountId%7D/orders/%7BorderId%7D-0
        ### Arguments:
        ----
        account {str} -- The account number that you want to place the order for.
        saved_order_id {str} --  The saved order id.
        
        ### Usage:
        ----
            >>> td_client.cancel_order(account = 'MyAccountID', saved_order_id = 'MyOrderID')
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """

        # define the endpoint
        endpoint = 'accounts/{}/savedorders/{}'.format(account, saved_order_id)
        return self._make_request(method='delete', endpoint=endpoint, order_details=True)


    def create_saved_order(self, account: str, saved_order: dict) -> dict:
        """Creates a saved order
        Creates a saved order for the specified account.
        ### Documentation:
        ----
        https://developer.tdameritrade.com/account-access/apis/delete/accounts/%7BaccountId%7D/orders/%7BorderId%7D-0
        ### Arguments:
        ----
        account {str} -- The account number that you want to place the order for.
        saved_order {dict} -- The order payload.
        ### Usage:
        ----
            >>> td_client.place_order(account='MyAccountID', saved_order={'orderKey':'OrderValue'})
        
        ### Returns:
        ----
        {dict} -- A response dicitonary.
        """

        # check to see if it's an order object.
        if isinstance(saved_order, Order):
            saved_order = saved_order._grab_order()
        else:
            saved_order = saved_order

        # make the request
        endpoint = 'accounts/{}/savedorders'.format(account)
        return self._make_request(method='post', endpoint=endpoint, mode='json', json=saved_order, order_details=True)

    def _create_token_timestamp(self, token_timestamp: str) -> int:
        """Parses the token and converts it to a timestamp.
        
        ### Arguments:
        ----
        token_timestamp {str} -- The timestamp returned from the get_user_principals endpoint.
        
        ### Returns:
        ----
        int -- the token timestamp as an integer.
        """

        token_timestamp = datetime.datetime.strptime(token_timestamp, "%Y-%m-%dT%H:%M:%S%z")
        token_timestamp = int(token_timestamp.timestamp()) * 1000

        return token_timestamp

    def create_streaming_session(self) -> TDStreamerClient:
        """Creates a new streaming session with the TD API.
        Grab the token to authenticate a stream session, builds
        the credentials payload, and initalizes a new instance
        of the TDStream client.
        ### Usage:
        ----
            >>> td_session = TDClient(
                client_id='<CLIENT_ID>',
                redirect_uri='<REDIRECT_URI>',
                credentials_path='<CREDENTIALS_PATH>'
            )
            >>> td_session.login()
            >>> td_stream_session = td_session.create_streaming_session()
        ### Returns:
        ----
        TDStreamerClient -- A new instance of a Stream Client that can be
            used to subscribe to different streaming services.
        """
        
        # Grab the Streamer Info.
        userPrincipalsResponse = self.get_user_principals(
            fields=['streamerConnectionInfo','streamerSubscriptionKeys','preferences','surrogateIds']
        )


        # Grab the timestampe.
        tokenTimeStamp = userPrincipalsResponse['streamerInfo']['tokenTimestamp']

        # Grab socket
        socket_url = userPrincipalsResponse['streamerInfo']['streamerSocketUrl']

        # Parse the token timestamp.
        tokenTimeStampAsMs = self._create_token_timestamp(
            token_timestamp=tokenTimeStamp
        )

        # Define our Credentials Dictionary used for authentication.
        credentials = {
            "userid": userPrincipalsResponse['accounts'][0]['accountId'],
            "token": userPrincipalsResponse['streamerInfo']['token'],
            "company": userPrincipalsResponse['accounts'][0]['company'],
            "segment": userPrincipalsResponse['accounts'][0]['segment'],
            "cddomain": userPrincipalsResponse['accounts'][0]['accountCdDomainId'],
            "usergroup": userPrincipalsResponse['streamerInfo']['userGroup'],
            "accesslevel": userPrincipalsResponse['streamerInfo']['accessLevel'],
            "authorized": "Y",
            "timestamp": tokenTimeStampAsMs,
            "appid": userPrincipalsResponse['streamerInfo']['appId'],
            "acl": userPrincipalsResponse['streamerInfo']['acl']
        }

        # Create the session
        streaming_session = TDStreamerClient(
            websocket_url=socket_url,
            user_principal_data=userPrincipalsResponse, 
            credentials=credentials,
        )

        return streaming_session