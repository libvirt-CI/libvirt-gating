import subprocess
import re
import locale
import argparse
import sys
import fcntl
import time
import signal
import os
import select
import xml.etree.ElementTree as ET

try:
    unicode
except NameError:
    unicode = str  # pylint:disable=W0622

COLOR= {
        'HEADER': '\033[35m',
        'PASS': '\033[32m',
        'SKIP': '\033[33m',
        'WARN': '\033[33m',
        'ERROR': '\033[31m',
        'FAIL': '\033[31m',
        'TIMEOUT': '\033[31m',
        'INVALID': '\033[31m',
        'BOLD': '\033[1m',
        'UNDERLINE': '\033[4m',
        'RUNNING': '\033[1m',
        }


class CmdResult(object):
    """
    A class representing the result of a system call.
    """

    def __init__(self, cmdline):
        self.cmdline = cmdline
        self.stdout = ""
        self.stdout_lines = []
        self.stderr = ""
        self.exit_code = None
        self.exit_status = "undefined"
        self.duration = 0.0

    def __str__(self):
        result = ''
        result += "command    : %s\n" % self.cmdline
        result += "exit_status: %s\n" % self.exit_status
        result += "exit_code  : %s\n" % self.exit_code
        result += "duration   : %s\n" % self.duration
        result += "stdout     :\n%s\n" % self.stdout
        result += "stderr     :\n%s\n" % self.stderr
        return result


class CmdError(Exception):
    """
    Exception class specifically used for `run` function
    """
    pass


def cmd_run(cmdline, timeout=1200, debug=False, ignore_fail=True):
    """
    Run the command line and return the result with a CmdResult object.

    :param cmdline: The command line to run.
    :type cmdline: str.
    :param timeout: After which the calling processing is killed.
    :type timeout: float.
    :param debug: Enable debug
    :type debug: boolean
    :param ignore_fail: Ingnore fail if set as True
    :type ignore_fail: boolen
    :returns: CmdResult -- the command result.
    :raises:
    """
    def _collect_output(stream, tag):
        collector = ""
        try:
            lines = stream.read()
            if lines:
                collector += lines
                if debug:
                    for line in lines.splitlines():
                        LOGGER.info('[%s] %s', tag, line)
        except IOError as detail:
            if detail.errno != errno.EAGAIN:
                raise
        return collector

    def _update_result():
        done = False
        exit_code = process.poll()
        result.duration = (time.time() - start)

        rl, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
        if process.stdout in rl:
            result.stdout += _collect_output(process.stdout, 'stdout')
        if process.stderr in rl:
            result.stderr += _collect_output(process.stderr, 'stderr')
        if exit_code is not None:
            result.exit_code = exit_code
            if exit_code == 0:
                result.exit_status = "success"
            else:
                result.exit_status = "failure"
            done = True

        if result.duration > timeout:
            done = True
        return done

    start = time.time()
    if debug:
        print('Running command "%s"' % cmdline)
    process = subprocess.Popen(
        cmdline,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        preexec_fn=os.setsid,
        universal_newlines=True,
    )

    fcntl.fcntl(
        process.stdout,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stdout, fcntl.F_GETFL) | os.O_NONBLOCK,
    )
    fcntl.fcntl(
        process.stderr,
        fcntl.F_SETFL,
        fcntl.fcntl(process.stderr, fcntl.F_GETFL) | os.O_NONBLOCK,
    )

    result = CmdResult(cmdline)

    try:
        while True:
            if _update_result():
                return result
    finally:
        if result.exit_code is None:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
            result.exit_status = "timeout"
        if result.exit_status != 'success' and not ignore_fail:
            if result.exit_status == "failure":
                raise CmdError("Command Failed:\n%s" % result)
            elif result.exit_status == 'timeout':
                raise CmdError("Command Timed out:\n%s" % result)
            else:
                raise CmdError("Unknown Error:\n%s" % result)


def std_output(string):
    """
    Print a string to stdout and flush it from cache
    """
    sys.stdout.write(string)
    sys.stdout.flush()


def escape(in_str):
    """
    Escape a string for HTML use.
    """
    out_str = (isinstance(in_str, (str, unicode)) and in_str or '%s' % in_str)
    out_str = out_str.replace('&', '&amp;')
    out_str = out_str.replace('<', '&lt;')
    out_str = out_str.replace('>', '&gt;')
    out_str = out_str.replace('"', "&quot;")
    return out_str


def decode_to_text(stream, encoding=locale.getpreferredencoding(),
                   errors='strict'):
    """
    Decode decoding string
    :param stream: string stream
    :param encoding: encode_type
    :param errors: error handling to use while decoding (strict,replace,
                   ignore,...)
    :return: encoding text
    """
    if hasattr(stream, 'decode'):
        return stream.decode(encoding, errors)
    if isinstance(stream, (str, unicode)):
        return stream
    raise TypeError("Unable to decode stream into a string-like type")


def list_test(cases, machine_type):
    """
    Get all specific type tests in avocado-vt.
    """
    only_str = ','.join(cases)
    tests = []
    res = cmd_run('avocado list --vt-type libvirt --vt-machine-type %s --vt-only-filter %s ' % (machine_type, only_str))
    res = decode_to_text(res.stdout)
    for line in res.splitlines():
        if re.match(r'VT\s+type_specific\.io-github-autotest-libvirt',
                    line):
            test = re.sub(r'VT\s+type_specific\.io-github-autotest-libvirt\.(.*)', r'\1', line)
            tests.append(test)
    tests_str = ' '.join(tests)
    gap_list = []
    for case in cases:
        if case.strip() not in tests_str:
            gap_list.append(case)
    if gap_list:
        print('****************************************************')
        print('*These cases are not found in tp-libvirt tests list*')
        print('****************************************************')
        for case in gap_list:
            print("%s" % case)
        print('****************************************************')
    return tests


def run_test(machine_type, vt_connect_uri, test_name):
    """
    Run a single test
    """
    def parse_result(result):
        """
        Parse result into variables loggable.
        """
        def _split_log(log_txt):
            """
            Split up logs
            """
            logs = []
            cur_line = ''
            for line in log_txt.splitlines():
                patt = r'.*(ERROR|INFO |WARNI|DEBUG)\|.*'
                if re.match(patt, line):
                    logs.append(cur_line)
                    cur_line = line
                else:
                    cur_line += line
            if cur_line:
                logs.append(cur_line)
            return logs

        lines = decode_to_text(result.stdout).splitlines()
        log_file = ''
        status = 'INVALID'
        for line in lines:
            if re.match(r' ?\(1/1\)', line):
                try:
                    status = line.split()[2]
                except IndexError:
                    pass
            if re.match(r'(JOB|DEBUG) LOG', line):
                log_file = line.split()[-1]

        if not log_file:
            print('Log file not found in result:\n%s' % result)
            return status, [], None

        logs = []
        try:
            with open(log_file) as log_fp:
                log_txt = log_fp.read()
                logs =_split_log(log_txt)
        except (IOError, OSError) as detail:
            print("Unable to read log file %s:\n%s" % (log_file, detail))
        return status, logs, log_file

    cmd = ('`which avocado` run --vt-type libvirt --vt-connect-uri %s '
           '--vt-machine-type %s %s' % (vt_connect_uri, machine_type, test_name))
    result = cmd_run(cmd, timeout=1800)
    status, logs, log_file = parse_result(result)

    if result.exit_status == 'timeout':
        status = 'TIMEOUT'

    result_line_pattern = (
        r'(ERROR|INFO )\| (FAIL|ERROR|PASS|SKIP|CANCEL|WARN|TEST_NA) \S+\s+(.*)$')
    result_line = ''
    for line in logs:
        matches = re.findall(result_line_pattern, line)
        if matches:
            match_text = matches[0][2]
            if match_text.startswith('-> '):
                match_text = match_text[3:]
            result_line += escape(match_text + '\n')

    log_dir = os.path.split(log_file)[0]
    xml_file = log_dir + '/results.xml'
    test_result = {
        'test': test_name,
        'status': status,
        'log_file': log_file,
        'logs': logs,
        'xml_file':xml_file,
        'result_line': result_line,
        'duration': result.duration
    }
    return test_result


def generate_etree_root():
    attr_dict = {}
    time_stamp = time.strftime("%d-%b-%Y_%H:%M:%S_UTC", time.gmtime(time.time()))
    attr_dict['time_stamp'] = time_stamp
    attr_dict['time_stamp_bare'] = str(time.time())
    attr_dict['name'] = 'avocado_vt_cases_%s' % time_stamp
    attr_dict['errors'] = '0'
    attr_dict['failures'] = '0'
    attr_dict['skipped'] = '0'
    attr_dict['tests'] = '0'
    attr_dict['time'] = '0'
    root = ET.Element('testsuite', attrib=attr_dict)
    return root, 'vtr_result_' + attr_dict['time_stamp']


def append_etree_element(test_result, root):
    if not os.path.isfile(test_result['xml_file']):
        root.attrib['errors'] = str(int(root.attrib['errors']) + 1)
        root.attrib['tests'] = str(int(root.attrib['tests']) + 1)
        attr_dict = {}
        attr_dict['name'] = test_result['test']
        error_case = ET.Element('testcase', attr_dict=attr_dict)
        error_ele = ET.Element('error')
        error_case.append(error_ele)
        error_case.text = str(test_result['logs'])
        root.append(error_case)
        return root
    tmp_tree = ET.parse(test_result['xml_file'])
    tmp_root = tmp_tree.getroot()
    for x in tmp_root:
        if test_result['status'] != 'PASS':
            x.text = str(test_result['logs'])
        x.attrib['name'] = test_result['test']
        root.append(x)
    root.attrib['errors'] = str(int(root.attrib['errors']) + int(tmp_root.attrib['errors']))
    root.attrib['failures'] = str(int(root.attrib['failures']) + int(tmp_root.attrib['failures']))
    root.attrib['skipped'] = str(int(root.attrib['skipped']) + int(tmp_root.attrib['skipped']))
    root.attrib['tests'] = str(int(root.attrib['tests']) + int(tmp_root.attrib['tests']))
    root.attrib['time'] = "%.3f" % (float(root.attrib['time']) + float(tmp_root.attrib['time']))
    return root


def prepare_guest():
    res = cmd_run('which systemctl', ignore_fail=True)
    if res.exit_status == 0:
        cmd_run('systemctl restart firewalld', ignore_fail=True)
        cmd_run('systemctl restart virtlogd')
        cmd_run('systemc restart libvirtd')
    else:
        cmd_run('service firewalld restart', ignore_fail=True)
        cmd_run('service virtlogd restart', ignore_fail=True)
        cmd_run('service libvirtd restart', ignore_fail=True)

    res = decode_to_text(cmd_run('virsh list --all').stdout)
    guest_list = res.splitlines()[2:-1]
    guest_installed=False
    for x in guest_list:
        if x.split()[1] == 'avocado-vt-vm1':
            guest_installed=True
            break
    if not guest_installed:
        cmd_run('virt-install --connect qemu:///system -n avocado-vt-vm1 --hvm --accelerate -r 2048 --vcpus=2 '
                '--disk path=/var/lib/avocado/data/avocado-vt/images/jeos-27-x86_64.qcow2,bus=virtio,format=qcow2 '
                '--network network=default,model=virtio --import --noreboot --noautoconsole --serial pty --debug '
                '--memballoon model=virtio --graphics vnc')


def _list(params):
    real_path = os.path.realpath(sys.argv[0])
    bin_dir_path = os.path.split(real_path)[0]
    dir_path = os.path.split(bin_dir_path)[0]
    if params['gating'] or not params.get('cases'):
        with open('%s/cases/gating.only' % dir_path, 'r') as case_file:
            cases = case_file.read().splitlines()
    else:
        cases = params['cases']
    legal_cases = list_test(cases, params['machine_type'])
    return legal_cases


def _run(params, legal_cases):
    prepare_guest()
    cases_count = len(legal_cases)
    pass_count = 0
    root, xml_file = generate_etree_root()
    for index, case in enumerate(legal_cases, start=1):
        output_line = '(%s/%s) %s \033[34mRUNNING\033[0m ' % (index, cases_count, case)
        std_output(output_line)
        test_result = run_test(params['machine_type'], params['vt_connect_uri'], case)
        root = append_etree_element(test_result, root)
        if test_result['status'] == 'PASS':
            pass_count += 1
            if not params['show_all']:
                std_output('\r' + len(output_line) * ' ' + '\r')
                continue
        status_color = COLOR['ERROR']
        if test_result['status'] in COLOR:
            status_color = COLOR[test_result['status']]
        std_output('\r(%s/%s) %s Result: \033[1m%s%s\033[0m %.2f s\n' % (
            index, cases_count, case, status_color, test_result['status'], test_result['duration']))
        std_output("    log file: %s \n" % test_result['log_file'])
    etree = ET.ElementTree(root)
    etree.write(xml_file, encoding='utf-8', )
    std_output('There are %s cases pass in %s cases\n' % (pass_count, cases_count))


class SubCMD(object):
    def __init__(self):
        self.subcommand_list = ['run', 'rerun', 'list']

    def list(self, params):
        legal_cases = _list(params)
        std_output('The cases list:\n')
        for case in legal_cases:
            std_output('%s\n' % case)

    def run(self, params):
        legal_cases = _list(params)
        _run(params, legal_cases)

    def rerun(self, params):
        legal_cases = []
        if params['xunit']:
            file = params['xunit']
        else:
            file_list = os.listdir()
            result_list = []
            for file in file_list:
                if file.startswith('vtr_result'):
                    time_stamp = file.split('_')[-3] + '_' +file.split('_')[-2]
                    time_stamp = time.strptime(time_stamp, "%d-%b-%Y_%H:%M:%S")
                    result_list.append([file, time_stamp])
            result_list = sorted(result_list, key=lambda x: x[1], reverse=True)
            file = result_list[0][0]
        etree = ET.parse(file)
        root = etree.getroot()
        for case in root:
            if not params['ignore_pass'] or (case.findall('error') or case.findall('skipped') or case.findall('failure')):
                legal_cases.append(case.attrib['name'])
        if not legal_cases:
            std_output('None case could be rerun\n')
            exit(1)
        _run(params, legal_cases)



def parser():
    parser = argparse.ArgumentParser()
    sub_parser = parser.add_subparsers(dest='subparser_name')

    run_parser = sub_parser.add_parser('run')
    rerun_parser = sub_parser.add_parser('rerun')
    list_parser = sub_parser.add_parser('list')

    run_parser.add_argument('--machine-type', dest='machine_type', action='store', default='q35')
    run_parser.add_argument('--vt-connect-uri', dest='vt_connect_uri', action='store', default='qemu:///system')
    run_parser.add_argument('--show-all', dest='show_all', action='store_true')
    run_parser.add_argument('--gating', dest='gating', action='store_true')
    run_parser.add_argument('cases', nargs='*')

    rerun_parser.add_argument('--machine-type', dest='machine_type', action='store', default='q35')
    rerun_parser.add_argument('--vt-connect-uri', dest='vt_connect_uri', action='store', default='qemu:///system')
    rerun_parser.add_argument('--show-all', dest='show_all', action='store_true')
    rerun_parser.add_argument('--ignore-pass', dest='ignore_pass', action='store_true')
    rerun_parser.add_argument('--xunit', dest='xunit', action='store', default='')

    list_parser.add_argument('--machine-type', dest='machine_type', action='store', default='q35')
    list_parser.add_argument('--gating', dest='gating', action='store_true')
    list_parser.add_argument('cases', nargs='*')
    return vars(parser.parse_args())


if __name__ == "__main__":
    params = parser()
    subcmd = SubCMD()
    if not params.get('subparser_name'):
        std_output('Please input a subcomand\n')
    elif params.get('subparser_name') not in subcmd.subcommand_list:
        std_output('Please input a right subcommand')
    else:
        subcommand = getattr(subcmd, params.get('subparser_name'))
        subcommand(params)
