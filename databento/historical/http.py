import os
from datetime import date
from json.decoder import JSONDecodeError
from typing import BinaryIO, List, Optional, Tuple, Union

import aiohttp
import pandas as pd
import requests
import zstandard
from aiohttp import ClientResponse
from databento.common.enums import Compression, Dataset, Encoding, Schema, SType
from databento.common.logging import log_info
from databento.common.parsing import (
    enum_or_str_lowercase,
    maybe_datetime_to_string,
    maybe_symbols_list_to_string,
)
from databento.historical.bento import BentoDiskIO, BentoMemoryIO
from databento.historical.error import BentoClientError, BentoServerError
from requests import Response
from requests.auth import HTTPBasicAuth


_NO_DATA_FOUND = b"No data found for query."
_16KB = 1024 * 16  # Backend standard streaming buffer size


class BentoHttpAPI:
    """The base class for all Databento HTTP API endpoints."""

    TIMEOUT = 100

    def __init__(self, key: str, gateway: str):
        self._key = key
        self._gateway = gateway
        self._headers = {"accept": "application/json"}

    @staticmethod
    def _timeseries_params(
        *,
        dataset: Union[Dataset, str],
        symbols: Optional[Union[List[str], str]] = None,
        schema: Schema,
        start: Optional[Union[pd.Timestamp, date, str, int]] = None,
        end: Optional[Union[pd.Timestamp, date, str, int]] = None,
        limit: Optional[int] = None,
        encoding: Encoding,
        compression: Compression,
        stype_in: SType,
        stype_out: SType = SType.PRODUCT_ID,
    ) -> List[Tuple[str, str]]:
        # Parse inputs
        dataset = enum_or_str_lowercase(dataset, "dataset")
        symbols = maybe_symbols_list_to_string(symbols)
        start = maybe_datetime_to_string(start)
        end = maybe_datetime_to_string(end)

        # Build params list
        params: List[Tuple[str, str]] = [
            ("dataset", dataset),
            ("symbols", symbols),
            ("schema", schema.value),
            ("start", start),
            ("end", end),
            ("encoding", encoding.value),
            ("compression", compression.value),
            ("stype_in", stype_in.value),
            ("stype_out", stype_out.value),
        ]

        if limit is not None:
            params.append(("limit", str(limit)))

        return params

    @staticmethod
    def _create_io(
        path: str,
        schema: Schema,
        encoding: Encoding,
        compression: Compression,
        overwrite: bool,
    ) -> Union[BentoMemoryIO, BentoDiskIO]:
        if path is None:
            return BentoMemoryIO(
                schema=schema,
                encoding=encoding,
                compression=compression,
            )
        else:
            # Check if file already exists and remove if overwriting
            if os.path.isfile(path):
                if overwrite:
                    os.remove(path)
                else:
                    raise FileExistsError(f"file already exists at '{path}'")
            return BentoDiskIO(
                path=path,
                schema=schema,
                encoding=encoding,
                compression=compression,
            )

    def _check_access_key(self):
        if self._key == "YOUR_ACCESS_KEY":
            raise ValueError(
                "The access key is currently set to 'YOUR_ACCESS_KEY'. "
                "Please replace this value with either a test or production "
                "access key. You will find these through your Databento dashboard.",
            )

    def _get(
        self,
        url: str,
        params: Optional[List[Tuple[str, str]]] = None,
        basic_auth: bool = False,
    ) -> Response:
        self._check_access_key()

        with requests.get(
            url=url,
            params=params,
            headers=self._headers,
            auth=HTTPBasicAuth(username=self._key, password=None)
            if basic_auth
            else None,
            timeout=(self.TIMEOUT, self.TIMEOUT),
        ) as response:
            check_http_error(response)
            return response

    async def _get_async(
        self,
        url: str,
        params: Optional[List[Tuple[str, str]]] = None,
        basic_auth: bool = False,
    ) -> ClientResponse:
        self._check_access_key()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=url,
                params=params,
                headers=self._headers,
                auth=aiohttp.BasicAuth(login=self._key, password="", encoding="utf-8")
                if basic_auth
                else None,
                timeout=self.TIMEOUT,
            ) as response:
                await check_http_error_async(response)
                return response

    def _post(
        self,
        url: str,
        params: Optional[List[Tuple[str, str]]] = None,
        basic_auth: bool = False,
    ) -> Response:
        self._check_access_key()

        with requests.post(
            url=url,
            params=params,
            headers=self._headers,
            auth=HTTPBasicAuth(username=self._key, password=None)
            if basic_auth
            else None,
            timeout=(self.TIMEOUT, self.TIMEOUT),
        ) as response:
            check_http_error(response)
            return response

    def _stream(
        self,
        url: str,
        params: List[Tuple[str, str]],
        basic_auth: bool,
        decompress: bool,
        binary_io: BinaryIO,
    ) -> None:
        self._check_access_key()

        with requests.get(
            url=url,
            params=params,
            headers=self._headers,
            auth=HTTPBasicAuth(username=self._key, password=None)
            if basic_auth
            else None,
            timeout=(self.TIMEOUT, self.TIMEOUT),
            stream=True,
        ) as response:
            check_http_error(response)

            # Setup bento I/O writer
            writer = binary_io
            if decompress:
                # Wrap writer with zstd decompressor
                writer = zstandard.ZstdDecompressor().stream_writer(binary_io)

            for chunk in response.iter_content(chunk_size=_16KB):
                if chunk == _NO_DATA_FOUND:
                    log_info("No data found for query.")
                    return
                writer.write(chunk)

    async def _stream_async(
        self,
        url: str,
        params: List[Tuple[str, Optional[str]]],
        basic_auth: bool,
        decompress: bool,
        binary_io: BinaryIO,
    ) -> None:
        self._check_access_key()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=url,
                params=[x for x in params if x[1] is not None],
                headers=self._headers,
                auth=aiohttp.BasicAuth(login=self._key, password="", encoding="utf-8")
                if basic_auth
                else None,
                timeout=self.TIMEOUT,
            ) as response:
                await check_http_error_async(response)

                # Setup bento I/O writer
                writer = binary_io
                if decompress:
                    # Wrap writer with zstd decompressor
                    writer = zstandard.ZstdDecompressor().stream_writer(binary_io)

                async for chunk in response.content.iter_chunks():
                    data: bytes = chunk[0]
                    if data == _NO_DATA_FOUND:
                        log_info("No data found for query.")
                        return
                    writer.write(data)


def is_400_series_error(status: int) -> bool:
    return status // 100 == 4


def is_500_series_error(status: int) -> bool:
    return status // 100 == 5


def check_http_error(response: Response) -> None:
    if is_500_series_error(response.status_code):
        try:
            json = response.json()
            message = json.get("detail")
        except JSONDecodeError:
            json = None
            message = None
        raise BentoServerError(
            http_status=response.status_code,
            http_body=response.content,
            json_body=json,
            message=message,
            headers=response.headers,
        )
    elif is_400_series_error(response.status_code):
        try:
            json = response.json()
            message = json.get("detail")
        except JSONDecodeError:
            json = None
            message = None
        raise BentoClientError(
            http_status=response.status_code,
            http_body=response.content,
            json_body=json,
            message=message,
            headers=response.headers,
        )


async def check_http_error_async(response: ClientResponse) -> None:
    if is_500_series_error(response.status):
        json = await response.json()
        raise BentoServerError(
            http_status=response.status,
            http_body=response.content,
            json_body=json,
            message=json["detail"],
            headers=response.headers,
        )
    elif is_400_series_error(response.status):
        json = await response.json()
        raise BentoClientError(
            http_status=response.status,
            http_body=response.content,
            json_body=json,
            message=json["detail"],
            headers=response.headers,
        )
