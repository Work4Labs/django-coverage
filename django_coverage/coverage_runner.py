"""
Copyright 2009 55 Minutes (http://www.55minutes.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
import os
from StringIO import StringIO
import sys

import django

if django.VERSION < (1, 2):
    msg = """

    django-coverage 1.1+ requires django 1.2+.
    Please use django-coverage 1.0.3 if you have django 1.1 or django 1.0
    """
    raise Exception(msg)

from django.conf import global_settings
from django.db.models import get_app, get_apps
from django.test.utils import get_runner

from coverage import coverage

from django_coverage import settings
from django_coverage.utils.coverage_report import html_report
from django_coverage.utils.module_tools import get_all_modules


DjangoTestSuiteRunner = get_runner(global_settings)


class CoverageRunner(DjangoTestSuiteRunner):
    """
    Test runner which displays a code coverage report at the end of the run.
    """

    def __new__(cls, *args, **kwargs):
        """
        Add the original test runner to the front of CoverageRunner's bases,
        so that CoverageRunner will inherit from it. This allows it to work
        with customized test runners.
        """
        # If the test runner was changed by the management command, change it
        # back to its original value in order to get the original runner.
        if getattr(settings, 'ORIG_TEST_RUNNER', None):
            settings.TEST_RUNNER = settings.ORIG_TEST_RUNNER
            TestRunner = get_runner(settings)
            if (TestRunner != DjangoTestSuiteRunner):
                cls.__bases__ = (TestRunner,) + cls.__bases__
        return super(CoverageRunner, cls).__new__(cls)

    def _get_app_package(self, app_model_module):
        """
        Returns the app module name from the app model module.
        """
        return '.'.join(app_model_module.__name__.split('.')[:-1])

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        cov = coverage(config_file=settings.COVERAGE_CONFIG_FILE)
        cov.use_cache(settings.COVERAGE_USE_CACHE)
        for e in settings.COVERAGE_CODE_EXCLUDES:
            cov.exclude(e)
        cov.start()
        results = super(CoverageRunner, self).run_tests(test_labels, extra_tests, **kwargs)
        cov.stop()

        coverage_modules = []
        if test_labels:
            for label in test_labels:
                label = label.split('.')[0]
                app = get_app(label)
                coverage_modules.append(self._get_app_package(app))
        else:
            for app in get_apps():
                coverage_modules.append(self._get_app_package(app))

        coverage_modules.extend(settings.COVERAGE_ADDITIONAL_MODULES)

        packages, modules, excludes, errors = get_all_modules(
            coverage_modules, settings.COVERAGE_MODULE_EXCLUDES,
            settings.COVERAGE_PATH_EXCLUDES)

        outfile = StringIO()
        coverage_value = cov.report(modules.values(), show_missing=1, outfile=outfile)
        if settings.COVERAGE_USE_STDOUT:
            print >>sys.stdout, outfile.getvalue()
            if excludes:
                message = "The following packages or modules were excluded:"
                print >>sys.stdout
                print >>sys.stdout, message,
                for e in excludes:
                    print >>sys.stdout, e,
                print >>sys.stdout
            if errors:
                message = "There were problems with the following packages "
                message += "or modules:"
                print >>sys.stdout
                print >>sys.stderr, message,
                for e in errors:
                    print >>sys.stderr, e,
                print >>sys.stdout

        outdir = settings.COVERAGE_REPORT_HTML_OUTPUT_DIR
        if outdir and settings.COVERAGE_OUTPUT_HTML_REPORT:
            outdir = os.path.abspath(outdir)
            if settings.COVERAGE_CUSTOM_REPORTS:
                html_report(outdir, modules, excludes, errors)
            else:
                cov.html_report(modules.values(), outdir)
            print >>sys.stdout
            print >>sys.stdout, "HTML reports were output to '%s'" %outdir

        coverage_fails = coverage_value < settings.COVERAGE_FAIL_UNDER
        if coverage_fails:
            msg = "Test coverage failed: %0.2f%% is less than %0.2f%% !" % (coverage_value, settings.COVERAGE_FAIL_UNDER)
            print >>sys.stdout, msg

        # from https://github.com/django/django/blob/master/django/core/management/commands/test.py#L90-L91
        return results or coverage_fails
