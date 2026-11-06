"""Reproduce the CPU graph using ONNX Runtime 1.21.1; originals stay unchanged."""
import hashlib
import importlib.util
from pathlib import Path
import onnx
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

ROOT = Path(__file__).resolve().parent
from build_paths import WORK
DEST = WORK / 'models'
assert ort.__version__ == '1.21.1'
spec = importlib.util.spec_from_file_location('hojo_model', ROOT / 'source/hojo-80m/upstream/Hojo-TTS-Light-80M/onnx_model.py')
hojo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hojo)
source = DEST / '80m/Hojo-TTS-Light-llm.onnx'
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'f232094e38bc64f0f6ab1d839e222314fb6b54c2a6f6fa6fb789909f590be326'
model = hojo._promote_bf16_onnx_to_fp32(onnx.load(source))
onnx.save(model, DEST / 'fp32-unoptimized.onnx')
del model
options = ort.SessionOptions()
options.intra_op_num_threads = 2
options.inter_op_num_threads = 1
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
options.optimized_model_filepath = str(DEST / 'fp32.onnx')
session = ort.InferenceSession(str(DEST / 'fp32-unoptimized.onnx'), options, providers=['CPUExecutionProvider'])
del session
quantize_dynamic(str(DEST / 'fp32.onnx'), str(DEST / 'int8.onnx'),
                 per_channel=True, reduce_range=False, weight_type=QuantType.QInt8,
                 op_types_to_quantize=['MatMul', 'Gemm'], extra_options={'MatMulConstBOnly': True})
onnx.checker.check_model(str(DEST / 'int8.onnx'))
print('INT8 SHA256:', hashlib.sha256((DEST / 'int8.onnx').read_bytes()).hexdigest())
