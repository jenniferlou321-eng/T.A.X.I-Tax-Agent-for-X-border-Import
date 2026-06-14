"""CN BrowserChannels for Chinese tax filing via etax.chinatax.gov.cn"""

from .cn_vat_channel import CNVATBrowserChannel
from .cn_cit_channel import CNCITBrowserChannel

__all__ = ["CNVATBrowserChannel", "CNCITBrowserChannel"]
