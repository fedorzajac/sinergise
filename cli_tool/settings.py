
import geopandas as gpd
from cli_tool.calculations import calculate_epsg
from dotenv import load_dotenv
import os

load_dotenv()

class Settings:

    def __init__(self, bb_file:str, api_url:str, data_collection: str = "sentinel-2-l2a"):
        from cli_tool.network import get_token
        self.epsg = calculate_epsg(file_path= bb_file)
        self.bb_file = bb_file
        self.api_url = api_url
        self.data_collection = data_collection
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.token_url = os.getenv("COPERNICUS_TOKEN_URL")
        token = get_token(client_id=self.client_id, client_secret=self.client_secret, url=self.token_url or "")
        if token is None:
            raise ValueError("Failed to get token")
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        pass

    pass
