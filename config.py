from pydantic import BaseSettings, Field, BaseModel, FilePath, EmailStr, HttpUrl
from typing import Optional
from pathlib import Path

class AppInfo(BaseModel):
    NAME: str = 'Radiant'
    URL: HttpUrl = 'https://github.com/drdbrr/webrok.git'
    EMAIL: EmailStr = 'stderr47@gmail.com'

    
    
class GlobalConfig(BaseSettings):
    CONTACT: AppInfo = AppInfo()
    ENV_STATE: Optional[str] = Field(None, env="ENV_STATE")
    
    HOST: Optional[str] = None
    PORT: Optional[int] = None
    DEBUG: Optional[bool] = None
    RELOAD: Optional[bool] = None
    LOG_LEVEL: Optional[str] = None
    
    SSL_KEY: Optional[FilePath] = None
    SSL_CERT: Optional[FilePath] = None
    
    REDIS_URL: Optional[str] = None
    
    TITLE: str = 'Webrok server'
    DESCRIPTION: str = 'Web based sigrok application'
    VERSION: str = '0.0.1'
    
    class Config:
        env_file: str = ".env"

class DevConfig(GlobalConfig):
    class Config:
        env_prefix: str = "DEV_"
        
class ProdConfig(GlobalConfig):
    class Config:
        env_prefix: str = "PROD_"
        
        
class FactoryConfig:
    def __init__(self, env_state: Optional[str]):
        self.env_state = env_state

    def __call__(self):
        if self.env_state == "dev":
            return DevConfig()

        elif self.env_state == "prod":
            return ProdConfig()
            
cnf = FactoryConfig(GlobalConfig().ENV_STATE)()

#print(cnf.dict())

