"""Check CPU numerical parity of the equivalent ConvTranspose padding rewrite.

Run with the separate Kokoro DirectML interpreter (onnx + onnxruntime required).
Fixtures and derived graphs are written under artifacts, never over real models.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper


def main():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('pvs_runner', root/'optional_engine_runner.py')
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    folder = root/'artifacts/kokoro-graph-parity'
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(731)
    checks = []
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    for group in (1, 2, 4):
        for length in (1, 2, 7, 19):
            channels = 2 * group
            weights = rng.normal(size=(channels, 2, 3)).astype(np.float32)
            bias = rng.normal(size=(channels,)).astype(np.float32)
            node = helper.make_node('ConvTranspose', ['x','w','b'], ['y'], name='padding-test',
                                    kernel_shape=[3], strides=[2], pads=[1,1],
                                    output_padding=[1], group=group)
            graph = helper.make_graph([node], 'test',
                [helper.make_tensor_value_info('x', TensorProto.FLOAT, [1,channels,length])],
                [helper.make_tensor_value_info('y', TensorProto.FLOAT, [1,channels,length*2])],
                [numpy_helper.from_array(weights,'w'),numpy_helper.from_array(bias,'b')])
            original = helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)])
            original.ir_version = 10
            onnx.checker.check_model(original)
            source = folder/f'groups-{group}-length-{length}.onnx'
            onnx.save(original,str(source))
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            rewritten = runner.kokoro_directml_model(source)
            changed = onnx.load(str(rewritten))
            onnx.checker.check_model(changed)
            assert [t.SerializeToString() for t in original.graph.initializer] == [t.SerializeToString() for t in changed.graph.initializer]
            x = rng.normal(size=(1,channels,length)).astype(np.float32)
            a = ort.InferenceSession(str(source),sess_options=options,providers=['CPUExecutionProvider']).run(None,{'x':x})[0]
            b = ort.InferenceSession(str(rewritten),sess_options=options,providers=['CPUExecutionProvider']).run(None,{'x':x})[0]
            error = float(np.max(np.abs(a-b)))
            assert a.shape==b.shape and np.allclose(a,b,rtol=1e-6,atol=1e-6)
            assert hashlib.sha256(source.read_bytes()).hexdigest()==before
            modified = rewritten.stat().st_mtime_ns
            assert runner.kokoro_directml_model(source)==rewritten
            assert rewritten.stat().st_mtime_ns==modified
            checks.append({'groups':group,'input_length':length,'max_absolute_error':error})
    (folder/'results.json').write_text(json.dumps({'status':'passed','cases':checks},indent=2))
    print(json.dumps({'status':'passed','cases':len(checks),'max_error':max(c['max_absolute_error'] for c in checks)}))


if __name__=='__main__':
    main()
