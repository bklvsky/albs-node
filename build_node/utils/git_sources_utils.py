import logging
import os
import re
import urllib.parse

from plumbum import local

from build_node.utils.file_utils import download_file


class BaseSourceDownloader:

    def __init__(self, sources_dir: str):
        self._sources_dir = sources_dir

    def find_metadata_file(self) -> str:
        for candidate in os.listdir(self._sources_dir):
            if re.search(r'^\..*\.metadata$', candidate):
                return os.path.join(self._sources_dir, candidate)
            elif candidate == 'sources':
                return os.path.join(self._sources_dir, candidate)

    def iter_source_records(self):
        metadata_file = self.find_metadata_file()
        if metadata_file is None:
            return
        for line in open(metadata_file, 'r').readlines():
            stripped = line.strip()
            if stripped.lower().startswith('sha512'):
                result = re.search(
                    r'SHA512\s+\((?P<source>.+)\)\s+=\s+(?P<checksum>[\w\d]+)',
                    line.strip(), re.IGNORECASE
                ).groupdict()
                checksum = result['checksum']
                path = result['source']
            else:
                checksum, path = line.strip().split()
            yield checksum, os.path.join(self._sources_dir, path)

    def download_all(self) -> bool:
        if not self.find_metadata_file():
            return False
        # TODO: instead of hardcoded name, we should create any path,
        #       needed by metadata file, not just "SOURCES"
        if not os.path.exists(os.path.join(self._sources_dir, 'SOURCES')):
            os.mkdir(os.path.join(self._sources_dir, 'SOURCES'))
        download_dict = {}
        for checksum, path in self.iter_source_records():
            try:
                self.download_source(checksum, path)
            except:
                logging.exception('Cannot download %s with checksum %s', path, checksum)
            else:
                download_dict[checksum] = True
        return all(download_dict.values())

    def download_source(self, checksum: str, dst_path: str) -> str:
        raise NotImplementedError()


class AlmaSourceDownloader(BaseSourceDownloader):

    blob_storage = 'https://sources.almalinux.org/'

    def download_source(self, checksum: str, download_path: str) -> str:
        full_url = urllib.parse.urljoin(self.blob_storage, checksum)
        # sources.almalinux.org doesn't accept default pycurl user-agent
        headers = ['User-Agent: Almalinux build node']
        return download_file(full_url, download_path, http_header=headers)


class CentpkgDowloader(BaseSourceDownloader):

    def download_source(self, checksum: str, dst_path: str) -> str:
        pass

    def download_all(self):
        sources_file = os.path.join(self._sources_dir, 'sources')
        if not os.path.isfile(sources_file):
            return False
        local['centpkg'].with_cwd(self._sources_dir).run(
            args=('sources', '--force'))
        return True
