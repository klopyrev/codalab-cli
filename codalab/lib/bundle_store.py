'''
BundleStore is a data store that stores actual bundle data. Bundles are logical
folders within this data store. This class provides two main methods:
  get_location: return the location of the folder with the given data hash.
  upload: upload a local directory to the store and return its data hash.
'''
import errno
import os
import time
import sys
import uuid
import tempfile

from codalab.lib import path_util, file_util, print_util, zip_util
from codalab.common import UsageError

class BundleStore(object):
    DATA_SUBDIRECTORY = 'data'
    TEMP_SUBDIRECTORY = 'temp'

    # The amount of time a folder can live in the data and temp
    # directories before it is garbage collected by full_cleanup.
    # Note: this is not used right now since we clear out the bundle store
    # immediately.
    DATA_CLEANUP_TIME = 60
    TEMP_CLEANUP_TIME = 60*60

    def __init__(self, codalab_home):
        '''
        codalab_home: data/ is where all the bundles are actually stored, temp/ is temporary
        '''
        self.codalab_home = path_util.normalize(codalab_home)
        self.data = os.path.join(self.codalab_home, self.DATA_SUBDIRECTORY)
        self.temp = os.path.join(self.codalab_home, self.TEMP_SUBDIRECTORY)
        self.make_directories()

    def _reset(self):
        '''
        Delete all stored bundles and then recreate the root directories.
        '''
        # Do not run this function in production!
        path_util.remove(self.data)
        path_util.remove(self.temp)
        self.make_directories()

    def make_directories(self):
        '''
        Create the data, and temp directories for this BundleStore.
        '''
        for path in (self.data, self.temp):
            path_util.make_directory(path)

    def get_location(self, data_hash, relative=False):
        '''
        Returns the on-disk location of the bundle with the given data hash.
        '''
        if relative:
            return data_hash
        return os.path.join(self.data, data_hash)

    def get_temp_location(self, identifier):
        '''
        Returns the on-disk location of the temporary bundle directory.
        '''
        return os.path.join(self.temp, identifier)

    def make_temp_location(self, identifier):
        '''
        Creates directory with given name under TEMP_SUBDIRECTORY
        '''
        path_util.make_directory(self.get_temp_location(identifier));


    def upload(self, sources, follow_symlinks, exclude_patterns, git, unpack, remove_sources):
        '''
        |sources|: specifies the locations of the contents to upload.  Each element is either a URL or a local path.
        |follow_symlinks|: for local path(s), whether to follow (resolve) symlinks
        |exclude_patterns|: for local path(s), don't upload these patterns (e.g., *.o)
        |git|: for URL, whether |source| is a git repo to clone.
        |unpack|: for each source in |sources|, whether to unpack it if it's an archive.
        |remove_sources|: remove |sources|.

        If |sources| contains one source, then the bundle contents will be that source.
        Otherwise, the bundle contents will be a directory with each of the sources.
        Exceptions:
        - If |git|, then each source is replaced with the result of running 'git clone |source|'
        - If |unpack| is True or a source is an archive (zip, tar.gz, etc.), then unpack the source.

        Install the contents of the directory at |source| into
        DATA_SUBDIRECTORY in a subdirectory named by a hash of the contents.

        Return a (data_hash, metadata) pair, where the metadata is a dict mapping
        keys to precomputed statistics about the new data directory.
        '''
        to_delete = []

        # Create temporary directory as a staging area and put everything there.
        temp_path = tempfile.mkdtemp('-bundle_store_upload')
        temp_subpaths = []
        for source in sources:
            # Where to save |source| to (might change this value if we unpack).
            temp_subpath = os.path.join(temp_path, os.path.basename(source))
            if remove_sources:
                to_delete.append(source)
            source_unpack = unpack and zip_util.path_is_archive(source)

            if path_util.path_is_url(source):
                # Download the URL.
                print_util.open_line('BundleStore.upload: downloading %s to %s' % (source, temp_path))
                if git:
                    file_util.git_clone(source, temp_subpath)
                else:
                    file_util.download_url(source, temp_subpath, print_status=True)
                    if source_unpack:
                        zip_util.unpack(temp_subpath, zip_util.strip_archive_ext(temp_subpath))
                        path_util.remove(temp_subpath)
                        temp_subpath = zip_util.strip_archive_ext(temp_subpath)
                print_util.clear_line()
            else:
                # Copy the local path.
                source_path = path_util.normalize(source)
                path_util.check_isvalid(source_path, 'upload')

                # Recursively copy the directory into a new BundleStore temp directory.
                print_util.open_line('BundleStore.upload: %s => %s' % (source_path, temp_subpath))
                if source_unpack:
                    zip_util.unpack(source_path, zip_util.strip_archive_ext(temp_subpath))
                    temp_subpath = zip_util.strip_archive_ext(temp_subpath)
                else:
                    if remove_sources:
                        path_util.rename(source_path, temp_subpath)
                    else:
                        path_util.copy(source_path, temp_subpath, follow_symlinks=follow_symlinks, exclude_patterns=exclude_patterns)
                print_util.clear_line()

            temp_subpaths.append(temp_subpath)

        # If exactly one source, then upload that directly.
        if len(temp_subpaths) == 1:
            to_delete.append(temp_path)
            temp_path = temp_subpaths[0]

        # Multiplex between uploading a directory and uploading a file here.
        # All other path_util calls will use these lists of directories and files.
        if os.path.isdir(temp_path):
            dirs_and_files = path_util.recursive_ls(temp_path)
        else:
            dirs_and_files = ([], [temp_path])

        # Hash the contents of the temporary directory, and then if there is no
        # data with this hash value, move this directory into the data directory.
        print_util.open_line('BundleStore.upload: hashing %s' % temp_path)
        data_hash = '0x%s' % (path_util.hash_directory(temp_path, dirs_and_files),)
        print_util.clear_line()
        print_util.open_line('BundleStore.upload: computing size of %s' % temp_path)
        data_size = path_util.get_size(temp_path, dirs_and_files)
        print_util.clear_line()
        final_path = os.path.join(self.data, data_hash)
        if os.path.exists(final_path):
            # Already exists, just delete it
            path_util.remove(temp_path)
        else:
            print >>sys.stderr, 'BundleStore.upload: moving %s to %s' % (temp_path, final_path)
            path_util.rename(temp_path, final_path)

        # Delete paths.
        for path in to_delete:
            if os.path.exists(path):
                path_util.remove(path)

        # After this operation there should always be a directory at the final path.
        assert(os.path.lexists(final_path)), 'Uploaded to %s failed!' % (final_path,)
        return (data_hash, {'data_size': data_size})

    def cleanup(self, model, data_hash, except_bundle_uuids, dry_run):
        '''
        If the given data hash is not needed by any bundle (not in
        except_bundle_uuids), delete the data.
        '''
        bundles = model.batch_get_bundles(data_hash=data_hash)
        if all(bundle.uuid in except_bundle_uuids for bundle in bundles):
            absolute_path = self.get_location(data_hash)
            print >>sys.stderr, "cleanup: data %s" % absolute_path
            if not dry_run:
                path_util.remove(absolute_path)

    def full_cleanup(self, model, dry_run):
        '''
        For each data hash in the store, check if it should be garbage collected and
        delete its data if so. In addition, delete any old temporary files.
        '''
        old_data_files = self.list_old_files(self.data, self.DATA_CLEANUP_TIME)
        for data_hash in old_data_files:
            self.cleanup(model, data_hash, [], dry_run)
        old_temp_files = self.list_old_files(self.temp, self.TEMP_CLEANUP_TIME)
        for temp_file in old_temp_files:
            temp_path = os.path.join(self.temp, temp_file)
            print >>sys.stderr, "cleanup: temp %s" % temp_path
            if not dry_run:
                path_util.remove(temp_path)

    def list_old_files(self, path, cleanup_time):
        cleanup_cutoff = time.time() - cleanup_time
        result = []
        for file in os.listdir(path):
            absolute_path = os.path.join(path, file)
            if path_util.getmtime(absolute_path) < cleanup_cutoff:
                result.append(file)
        return result
