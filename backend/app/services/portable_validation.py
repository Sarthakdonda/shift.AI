"""Execute the fixed browser validator in a bounded child process, without platform secrets."""
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from app.core.errors import AppError


def run_process(args,cwd,timeout,env,memory_mb=4096):
    job=None
    kwargs={'start_new_session':True} if os.name!='nt' else {'creationflags':subprocess.CREATE_NO_WINDOW}
    process=subprocess.Popen(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',**kwargs)
    try:
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateJobObjectW.restype=wintypes.HANDLE
            kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
            kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
            kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
            kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            class Basic(ctypes.Structure):
                _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
            class IO(ctypes.Structure):
                _fields_=[(name,ctypes.c_ulonglong) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
            class Limits(ctypes.Structure):
                _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
            job=kernel.CreateJobObjectW(None,None)
            limits=Limits();limits.BasicLimitInformation.LimitFlags=0x2000|0x200|0x8
            limits.BasicLimitInformation.ActiveProcessLimit=100;limits.JobMemoryLimit=memory_mb*1024*1024
            if not job or not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,wintypes.HANDLE(int(process._handle))):
                process.kill()
                raise AppError('Unable to enforce worker process isolation.',503,'worker_isolation')
        stdout,stderr=process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
    except subprocess.TimeoutExpired:
        raise AppError('Build exceeded its time limit; its worker processes were stopped.',503,'build_timeout') from None
    finally:
        if job:
            kernel.CloseHandle(job)
        elif process.poll() is None:
            if os.name=='nt':process.kill()
            else:os.killpg(process.pid,signal.SIGKILL)
        if process.poll() is None:process.wait(timeout=10)


def validate(files):
    import shutil
    script=Path(__file__).resolve().parents[2]/'build-tools/validate-portable.cjs'
    if not (script.parent/'node_modules/playwright').exists() or not shutil.which('node'):
        raise AppError('Install backend/build-tools dependencies and its Chromium browser on the build worker.',503,'browser_configuration')
    with tempfile.TemporaryDirectory(prefix='shift-portable-') as directory:
        root=Path(directory).resolve()
        for name,text in files.items():
            path=(root/name).resolve()
            if not path.is_relative_to(root):raise AppError('Invalid application file path.',422)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMFILES','PLAYWRIGHT_BROWSERS_PATH'}}
        result=run_process([shutil.which('node'),str(script),str(root)],script.parent,150,env,2048)
        if result.returncode:
            raise AppError((result.stderr or result.stdout)[-5000:],422,'application_validation')
        try:
            outcome=json.loads(result.stdout.strip().splitlines()[-1])
            if outcome['status']!='passed' or not outcome['checks']:raise ValueError()
            return outcome
        except (ValueError,KeyError,IndexError):
            raise AppError('Browser validation did not return confirmed test results.',422,'application_validation') from None
