# coding=utf-8
import sys
import os
import shutil
import tempfile

from . import xml_utils
from . import fs_utils
from . import system

from ..__init__ import JAR_PATH
from ..__init__ import TMP_DIR


JAVA_PATH = 'java'
JAR_TRANSFORM = JAR_PATH + '/saxonb9-1-0-8j/saxon9.jar'
JAR_VALIDATE = JAR_PATH + '/XMLCheck.jar'

VALIDATE_COMMAND = 'java -cp "{JAR_VALIDATE}" br.bireme.XMLCheck.XMLCheck "{xml}" {validation_type}>"{result}"'


def validate_command(xml_filename, validation_type, result_filename):
    return VALIDATE_COMMAND.format(
        JAR_VALIDATE=JAR_VALIDATE,
        xml=xml_filename,
        validation_type=validation_type,
        result_filename=result_filename)


if not os.path.isdir(TMP_DIR):
    os.makedirs(TMP_DIR)


def format_parameters(parameters):
    r = ''
    for k, v in parameters.items():
        if v != '':
            if ' ' in v:
                r += k + '=' + '"' + v + '" '
            else:
                r += k + '=' + v + ' '
    return r


class XML(object):

    def __init__(self, xml, doctype=None):
        self.xml_filename = xml if not '<' in xml else None
        self.content = xml if '<' in xml else fs_utils.read_file(xml)
        self.doctype = doctype
        self.logger = None
        if doctype is not None:
            self._backup_xml_file()
            self._change_doctype()

    def _backup_xml_file(self):
        if self.logger is not None:
            self.logger.register('XML._backup_xml_file - inicio')
        self.backup_path = tempfile.mkdtemp()
        self.backup_xml_filename = self.backup_path + '/' + os.path.basename(self.xml_filename)
        shutil.copyfile(self.xml_filename, self.backup_xml_filename)
        if self.logger is not None:
            self.logger.register('XML._backup_xml_file - fim')

    def finish(self):
        if self.logger is not None:
            self.logger.register('XML.finish - inicio')
        if self.doctype is not None:
            shutil.move(self.backup_xml_filename, self.xml_filename)
            try:
                shutil.rmtree(self.backup_path)
            except:
                pass
        if self.logger is not None:
            self.logger.register('XML.finish - fim')

    def _change_doctype(self):
        if self.logger is not None:
            self.logger.register('XML._change_doctype - inicio')
        self.content = self.content.replace('\r\n', '\n')
        if '<!DOCTYPE' in self.content:
            find_text = self.content[self.content.find('<!DOCTYPE'):]
            find_text = find_text[0:find_text.find('>')+1]
            if len(find_text) > 0:
                if len(self.doctype) > 0:
                    self.content = self.content.replace(find_text, self.doctype)
                else:
                    if find_text + '\n' in self.content:
                        self.content = self.content.replace(find_text + '\n', self.doctype)
        elif self.content.startswith('<?xml '):
            if '?>' in self.content:
                xml_proc = self.content[0:self.content.find('?>')+2]
            xml = self.content[1:]
            if '<' in xml:
                xml = xml[xml.find('<'):]
            if len(self.doctype) > 0:
                self.content = xml_proc + '\n' + self.doctype + '\n' + xml
            else:
                self.content = xml_proc + '\n' + xml
        fs_utils.write_file(self.xml_filename, self.content)
        if self.logger is not None:
            self.logger.register('XML._change_doctype - fim')

    def transform_content(self, xsl_filename):
        if self.logger is not None:
            self.logger.register('XML.transform_content - inicio')
        f = tempfile.NamedTemporaryFile(delete=False)
        f.close()

        f2 = tempfile.NamedTemporaryFile(delete=False)
        f2.close()

        fs_utils.write_file(f.name, self.content)

        content = ''
        if self.transform_file(f.name, xsl_filename, f2.name):
            content = fs_utils.read_file(f2.name)

        for item in [f.name, f2.name]:
            fs_utils.delete_file_or_folder(f.name)
        if self.logger is not None:
            self.logger.register('XML.transform_content - fim')
        return content

    def prepare(self, result_filename):
        if self.logger is not None:
            self.logger.register('XML.prepare - inicio')
        temp_result_filename = TMP_DIR + '/' + os.path.basename(result_filename)
        result_path = os.path.dirname(result_filename)
        if not os.path.isdir(result_path):
            os.makedirs(result_path)
        for f in [result_filename, temp_result_filename]:
            fs_utils.delete_file_or_folder(f)
        if self.logger is not None:
            self.logger.register('XML.prepare - fim')
        return temp_result_filename

    def transform_file(self, xsl_filename, result_filename, parameters={}):
        if self.logger is not None:
            self.logger.register('XML.transform_file - inicio')
        error = False

        temp_result_filename = self.prepare(result_filename)

        if self.logger is not None:
            self.logger.register('XML.transform_file - command - inicio')
        cmd = JAVA_PATH + ' -jar "' + JAR_TRANSFORM + '" -novw -w0 -o "' + temp_result_filename + '" "' + self.xml_filename + '" "' + xsl_filename + '" ' + format_parameters(parameters)
        system.run_command(cmd)
        if self.logger is not None:
            self.logger.register('XML.transform_file - command - fim')

        if not os.path.exists(temp_result_filename):
            fs_utils.write_file(temp_result_filename, 'ERROR: transformation error.\n' + cmd)
            error = True
        shutil.move(temp_result_filename, result_filename)
        if self.logger is not None:
            self.logger.register('XML.transform_file - fim')

        return (not error)

    def xml_validate(self, result_filename):
        if self.logger is not None:
            self.logger.register('XML.xml_validate - inicio')
        validation_type = '' if self.doctype == '' else '--validate'
        temp_result_filename = self.prepare(result_filename)

        if self.logger is not None:
            self.logger.register('XML.transform_file - command - inicio')
        cmd = JAVA_PATH + ' -cp "' + JAR_VALIDATE + '" br.bireme.XMLCheck.XMLCheck "' + self.xml_filename + '" ' + validation_type + '>"' + temp_result_filename + '"'
        system.run_command(cmd)
        if self.logger is not None:
            self.logger.register('XML.transform_file - command - fim')

        if os.path.exists(temp_result_filename):
            result = fs_utils.read_file(temp_result_filename, sys.getfilesystemencoding())
            if 'ERROR' in result.upper():
                n = 0
                s = ''
                for line in fs_utils.read_file_lines(self.xml_filename):
                    if n > 0:
                        s += str(n) + ':' + line
                    n += 1
                result += '\n' + s
                fs_utils.write_file(result_filename, result)
                fs_utils.delete_file_or_folder(temp_result_filename)
            else:
                shutil.move(temp_result_filename, result_filename)
        else:
            result = 'ERROR: Not valid. Unknown error.\n' + cmd
            fs_utils.write_file(result_filename, result)
        if self.logger is not None:
            self.logger.register('XML.transform_file - command - fim')
        if self.logger is not None:
            self.logger.register('XML.xml_validate - fim')
        return not 'ERROR' in result.upper()


def xml_content_transform(content, xsl_filename):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()

    fs_utils.write_file(f.name, content)

    f2 = tempfile.NamedTemporaryFile(delete=False)
    f2.close()
    if xml_transform(f.name, xsl_filename, f2.name):
        content = fs_utils.read_file(f2.name)
        fs_utils.delete_file_or_folder(f2.name)
    fs_utils.delete_file_or_folder(f.name)
    return content


def xml_transform(xml_filename, xsl_filename, result_filename, parameters={}):
    #register_log('xml_transform: inicio')
    error = False

    temp_result_filename = TMP_DIR + '/' + os.path.basename(result_filename)

    if not os.path.isdir(os.path.dirname(result_filename)):
        os.makedirs(os.path.dirname(result_filename))
    for f in [result_filename, temp_result_filename]:
        fs_utils.delete_file_or_folder(f)
    tmp_xml_filename = create_temp_xml_filename(xml_filename)
    cmd = JAVA_PATH + ' -jar "' + JAR_TRANSFORM + '" -novw -w0 -o "' + temp_result_filename + '" "' + tmp_xml_filename + '" "' + xsl_filename + '" ' + format_parameters(parameters)
    system.run_command(cmd)
    if not os.path.exists(temp_result_filename):
        fs_utils.write_file(temp_result_filename, 'ERROR: transformation error.\n' + cmd)
        error = True
    shutil.move(temp_result_filename, result_filename)

    fs_utils.delete_file_or_folder(tmp_xml_filename)
    #register_log('xml_transform: fim')

    return (not error)


def xml_validate(xml_filename, result_filename, doctype=None):
    #register_log('xml_validate: inicio')
    #41    0.025    0.001   20.136    0.491 java_xml_utils.py:152(xml_validate)
    #41    0.009    0.000   19.997    0.488 java_xml_utils.py:150(xml_validate)
    #41    0.009    0.000   21.515    0.525 java_xml_utils.py
    #41    0.024    0.001   19.913    0.486 java_xml_utils.py:161(xml_validate)
    validation_type = ''

    if doctype is None:
        doctype = ''
    else:
        validation_type = '--validate'

    bkp = fs_utils.read_file(xml_filename)
    xml_utils.new_apply_dtd(xml_filename, doctype)
    temp_result_filename = TMP_DIR + '/' + os.path.basename(result_filename)
    fs_utils.delete_file_or_folder(result_filename)
    fs_utils.delete_file_or_folder(temp_result_filename)
    if not os.path.isdir(os.path.dirname(result_filename)):
        os.makedirs(os.path.dirname(result_filename))

    cmd = validate_command(xml_filename, validation_type, temp_result_filename)
    system.run_command(cmd)

    if os.path.exists(temp_result_filename):
        result = fs_utils.read_file(temp_result_filename, sys.getfilesystemencoding())

        if 'ERROR' in result.upper():
            lines = fs_utils.read_file_lines(xml_filename)
            numbers = [str(i) + ':' for i in range(1, len(lines)+1)]
            result = '\n'.join([n + line for n, line in zip(numbers, lines)])
            print(result)
            fs_utils.write_file(temp_result_filename, result)
    else:
        result = 'ERROR: Not valid. Unknown error.\n' + cmd
        fs_utils.write_file(temp_result_filename, result)

    shutil.move(temp_result_filename, result_filename)
    fs_utils.write_file(xml_filename, bkp)
    return 'ERROR' not in result.upper()


def new_xml_validate(xml_filename, result_filename, doctype=None):
    #register_log('xml_validate: inicio')
    validation_type = ''

    if doctype is None:
        doctype = ''
    else:
        validation_type = '--validate'

    bkp_xml_filename = xml_utils.apply_dtd(xml_filename, doctype)
    temp_result_filename = TMP_DIR + '/' + os.path.basename(result_filename)
    result_path = os.path.dirname(result_filename)
    fs_utils.delete_file_or_folder(result_filename)
    if not os.path.isdir(result_path):
        os.makedirs(result_path)

    cmd = JAVA_PATH + ' -cp "' + JAR_VALIDATE + '" br.bireme.XMLCheck.XMLCheck "' + xml_filename + '" ' + validation_type + '>"' + temp_result_filename + '"'
    system.run_command(cmd)

    if os.path.exists(temp_result_filename):
        result = fs_utils.read_file(temp_result_filename, sys.getfilesystemencoding())

        if 'ERROR' in result.upper():
            n = 0
            s = ''
            for line in fs_utils.read_file_lines(xml_filename):
                if n > 0:
                    s += str(n) + ':' + line
                n += 1
            result += '\n' + s.decode('utf-8')
            fs_utils.write_file(temp_result_filename, result)
    else:
        result = 'ERROR: Not valid. Unknown error.\n' + cmd
        fs_utils.write_file(temp_result_filename, result)

    shutil.move(temp_result_filename, result_filename)
    shutil.move(bkp_xml_filename, xml_filename)
    #register_log('xml_validate: fim')
    return not 'ERROR' in result.upper()


def create_temp_xml_filename(xml_filename):
    tmp_filename = TMP_DIR + '/' + os.path.basename(xml_filename)
    shutil.copyfile(xml_filename, tmp_filename)
    return tmp_filename