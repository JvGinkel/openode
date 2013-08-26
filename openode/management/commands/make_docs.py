import subprocess, os
from django.core.management.base import NoArgsCommand
import openode

DOC_DIR = os.path.join(openode.get_install_directory(), 'doc')

class Command(NoArgsCommand):
    def handle_noargs(self, **options):
        os.chdir(DOC_DIR)
        subprocess.call(['make', 'html'])

