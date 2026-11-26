"""Optional extra KDF backends for synthetic benchmarking, not production use."""
import ctypes as C, ctypes.util, hashlib, os, json
from pathlib import Path
from functools import lru_cache
HERE=Path(__file__).resolve().parent

def balloon_python(p,s,blocks,passes):
    # Single-lane Balloon SHA-256 (delta=3), 64-bit little-endian counters.
    counter=0
    def h(*args):
        nonlocal counter
        data=hashlib.sha256(counter.to_bytes(8,'little')+b''.join(args)).digest();counter+=1
        return data
    b=[h(p,s)]
    for _ in range(1,blocks): b.append(h(b[-1]))
    for t in range(passes):
        for m in range(blocks):
            b[m]=h(b[(m-1)%blocks],b[m])
            for i in range(3):
                index=hashlib.sha256(t.to_bytes(8,'little')+m.to_bytes(8,'little')+i.to_bytes(8,'little')).digest()
                other=int.from_bytes(h(s,index),'little')%blocks
                b[m]=h(b[m],b[other])
    return b[-1]

@lru_cache(None)
def nettle():
    path=os.environ.get('EXP5F_NETTLE') or ctypes.util.find_library('nettle')
    if not path: raise RuntimeError('libnettle unavailable')
    lib=C.CDLL(path); lib.nettle_balloon_itch.argtypes=[C.c_size_t,C.c_size_t];lib.nettle_balloon_itch.restype=C.c_size_t
    lib.nettle_balloon_sha256.argtypes=[C.c_size_t,C.c_size_t,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p,C.c_void_p];lib.nettle_balloon_sha256.restype=None
    return lib

def balloon_native(p,s,b,t):
    lib=nettle(); scratch=C.create_string_buffer(lib.nettle_balloon_itch(32,b)); out=C.create_string_buffer(32)
    lib.nettle_balloon_sha256(b,t,len(p),p,len(s),s,scratch,out);return out.raw

@lru_cache(None)
def phs_lib(kind):
    key='EXP5F_'+kind.upper(); path=os.environ.get(key)
    if not path:
        for ext in ('.dll','.so','.dylib'):
            x=HERE/'native'/('lib'+kind+ext)
            if x.exists(): path=str(x);break
    if not path: raise RuntimeError(f'{key} is not configured')
    lib=C.CDLL(str(Path(path).resolve()))
    f=lib.PHS;f.argtypes=[C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_size_t,C.c_uint,C.c_uint];f.restype=C.c_int
    return lib

def phs(kind,p,s,t,m):
    out=C.create_string_buffer(32); buf=C.create_string_buffer(p); salt=C.create_string_buffer(s)
    rc=phs_lib(kind).PHS(out,32,buf,len(p),salt,len(s),t,m)
    if rc!=0: raise RuntimeError(f'{kind} PHS returned {rc}')
    return out.raw

def yescrypt_python_binding(p,s,n,r):
    from pyescrypt import Yescrypt, Mode
    # JSON is the documented binding API. Normalize the deterministic serialized
    # result to 32 bytes for cascading. This serialization+SHA256 is included in timing.
    obj=Yescrypt(n=n,r=r,p=1,mode=Mode.JSON)
    result=obj.digest(password=p,salt=s)
    if isinstance(result,str): result=result.encode()
    if not isinstance(result,bytes): raise TypeError('Unexpected pyescrypt result type')
    return hashlib.sha256(result).digest()

@lru_cache(None)
def libcrypt():
    path=ctypes.util.find_library('crypt')
    if not path or os.name=='nt': raise RuntimeError('libxcrypt unavailable')
    lib=C.CDLL(path); f=lib.crypt_gensalt_rn;f.argtypes=[C.c_char_p,C.c_ulong,C.c_char_p,C.c_int,C.c_void_p,C.c_int];f.restype=C.c_char_p
    lib.crypt.argtypes=[C.c_char_p,C.c_char_p];lib.crypt.restype=C.c_char_p
    return lib

def yescrypt_mcf(p,s,cost):
    # libcrypt crypt() has process-local static storage. The benchmark runs
    # one task at a time in each process, never concurrently in threads.
    lib=libcrypt(); buf=C.create_string_buffer(192)
    if not lib.crypt_gensalt_rn(b'$y$',cost,s,len(s),buf,len(buf)):raise RuntimeError('yescrypt gensalt failed')
    out=lib.crypt(p.hex().encode(),buf.value)
    if not out or not out.startswith(b'$y$'):raise RuntimeError('yescrypt crypt failed')
    return hashlib.sha256(out).digest()

def stage(s,p,salt):
    k=s['kind']
    if k=='balloon':
        f=balloon_native if s['backend']=='nettle' else balloon_python
        return f(p,salt,s['blocks'],s['passes'])
    if k=='yescrypt': return yescrypt_mcf(p,salt,s['cost']) if s.get('backend')=='libxcrypt' else yescrypt_python_binding(p,salt,s['n'],s['r'])
    if k in ('catena','lyra2'): return phs(k,p,salt,s['t'],s['m_cost'])
    raise ValueError(k)

VECTORS=[(b'hunter42',b'examplesalt',1024,3,'716043dff777b44aa7b88dcbab12c078abecfac9d289c5b5195967aa63440dfb'),(b'password',b'salt',3,3,'a4df347f5a312e8b2b14c32164f61a81758c807f1bdcda44f4930e2b80ab2154'),(b'password',b'salt',1,1,'eefda4a8a75b461fa389c1dcfaf3e9dfacbc26f81f22e6f280d15cc18c417545')]

def discover():
    results={}
    for p,s,b,t,expected in VECTORS:
        assert balloon_python(p,s,b,t).hex()==expected, 'Balloon Python known-answer mismatch'
    results['balloon']={'available':True,'backend':'python','validation':'3 published Nettle vectors; Python reference performance only'}
    try:
        for p,s,b,t,expected in VECTORS: assert balloon_native(p,s,b,t).hex()==expected
        results['balloon']={'available':True,'backend':'nettle','validation':'3 published Nettle vectors'}
    except Exception as e: results['balloon']['native_unavailable']=str(e)
    # Independently published KATs are not bundled for these optional backends.
    # Only use them for exploratory timing until upstream vectors are checked.
    for k,spec in [('yescrypt',{'kind':'yescrypt','n':1024,'r':8}),('lyra2',{'kind':'lyra2','m_cost':16,'t':1}),('catena',{'kind':'catena','m_cost':8,'t':2})]:
        try:
            p=b'exp5f fixture'; salt=b'0123456789abcdef'; a=stage(spec,p,salt)
            assert len(a)==32 and a==stage(spec,p,salt) and a!=stage(spec,p+b'!',salt) and a!=stage(spec,p,salt[::-1])
            results[k]={'available':True,'backend':'pyescrypt JSON+SHA256' if k=='yescrypt' else 'external PHS shared library','validation':'determinism/input sensitivity only; independent KAT pending'}
        except Exception as e:
            results[k]={'available':False,'reason':f'{type(e).__name__}: {e}','validation':'not run'}
            if k=='yescrypt':
                try:
                    p=b'exp5f fixture'; salt=b'0123456789abcdef'; a=yescrypt_mcf(p,salt,3)
                    assert a==yescrypt_mcf(p,salt,3) and a!=yescrypt_mcf(p+b'!',salt,3) and a!=yescrypt_mcf(p,salt[::-1],3)
                    results[k]={'available':True,'backend':'libxcrypt','validation':'determinism/input sensitivity only; independent KAT pending'}
                except Exception as fallback:results[k]['libxcrypt_reason']=str(fallback)
    return results
