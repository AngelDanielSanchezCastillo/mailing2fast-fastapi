"""
Mail manager for handling multiple SMTP accounts
"""

from typing import Dict, Optional

from .sender import EmailSender
from .settings import MailSettings, settings


class MailManager:
    """
    Manages multiple EmailSender instances for different SMTP accounts.
    
    This class provides:
    - Lazy sender creation (senders created only when first accessed)
    - Multiple named SMTP accounts support
    - Centralized sender management
    - Easy access to configured accounts
    """

    def __init__(self, config: MailSettings):
        """
        Initialize the mail manager.
        
        Args:
            config: Mail settings configuration
        """
        self.config = config
        self._senders: Dict[str, EmailSender] = {}

    def get_sender(self, account_name: Optional[str] = None) -> EmailSender:
        """
        Get or create an EmailSender for a specific SMTP account.
        
        Args:
            account_name: Name of the SMTP account. If None, uses default_account.
            
        Returns:
            EmailSender for the requested account.
            
        Raises:
            ValueError: If account doesn't exist.
            
        Example:
            manager = get_manager()
            
            # Get default sender
            sender = manager.get_sender()
            
            # Get specific account sender
            support_sender = manager.get_sender("support")
        """
        name = account_name or self.config.default_account
        
        # Return existing sender if already created
        if name in self._senders:
            return self._senders[name]
        
        # Verify account exists
        if not self.config.has_account(name):
            available = ", ".join(self.config.smtp_accounts.keys())
            raise ValueError(
                f"SMTP account '{name}' not found. Available accounts: {available}"
            )
        
        # Create sender with account-specific configuration
        # We create a modified config that sets this account as default
        # so the sender uses it automatically
        account_config = self.config.model_copy(deep=True)
        account_config.default_account = name
        
        sender = EmailSender(account_config)
        
        # Store sender
        self._senders[name] = sender
        
        return sender

    def list_accounts(self) -> list[str]:
        """
        List all configured SMTP account names.
        
        Returns:
            List of account names.
            
        Example:
            manager = get_manager()
            accounts = manager.list_accounts()
            print(f"Available accounts: {accounts}")
        """
        return list(self.config.smtp_accounts.keys())

    def has_account(self, account_name: str) -> bool:
        """
        Check if an SMTP account exists.
        
        Args:
            account_name: Name of the account to check.
            
        Returns:
            True if account exists, False otherwise.
            
        Example:
            manager = get_manager()
            if manager.has_account("support"):
                sender = manager.get_sender("support")
        """
        return self.config.has_account(account_name)

    def get_default_account(self) -> str:
        """
        Get the name of the default SMTP account.
        
        Returns:
            Name of the default account.
        """
        return self.config.default_account


# Global singleton instance
_manager: Optional[MailManager] = None


def get_manager(config: Optional[MailSettings] = None) -> MailManager:
    """
    Get the global MailManager singleton.
    
    Args:
        config: Optional mail settings. If not provided, uses global settings.
        
    Returns:
        MailManager singleton instance.
        
    Example:
        # Get manager with default settings
        manager = get_manager()
        
        # Get manager with custom settings
        custom_settings = MailSettings(...)
        manager = get_manager(custom_settings)
    """
    global _manager
    
    if _manager is None:
        cfg = config or settings
        _manager = MailManager(cfg)
    
    return _manager
