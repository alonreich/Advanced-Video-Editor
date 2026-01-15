import uuid
import logging

class FilterNode:
    """Represents a single filter in an FFmpeg filter graph."""
    
    def __init__(self, name, params=None, num_inputs=1, num_outputs=1):
        self.name = name
        self.params = params
        self.input_pins = [None] * num_inputs
        self.output_pins = [f"[{self._generate_pin_id()}]" for _ in range(num_outputs)]
        
    def _generate_pin_id(self):
        return f"stream_{uuid.uuid4().hex[:8]}"

    def __str__(self):
        """Generates the string representation of the filter node."""
        logger = logging.getLogger("Advanced_Video_Editor")
        inputs = "".join(str(pin) for pin in self.input_pins if pin)
        outputs = "".join(self.output_pins)
        param_str = ""
        if self.params:
            if isinstance(self.params, dict):
                param_str = "=" + ":".join([f"{k}={v}" for k, v in self.params.items()])
            elif isinstance(self.params, str):
                param_str = f"={self.params}"
        result = f"{inputs}{self.name}{param_str}{outputs}"
        logger.debug(f"[FILTER_NODE] Generated string: {result}")
        return result

class FilterGraph:
    """Manages a collection of FilterNodes and their connections."""
    
    def __init__(self):
        self.nodes = []
        self._inputs = []
        self._input_map = {}

    def add_input(self, file_path):
        """Adds a file as an input source for the graph."""
        norm_path = file_path.replace('\\', '/')
        if norm_path not in self._input_map:
            self._input_map[norm_path] = len(self._inputs)
            self._inputs.append(norm_path)
        return self._input_map[norm_path]

    def get_input_stream(self, file_path, stream_type='v'):
        """Gets a pin for a specific input stream (e.g., '[0:v]')."""
        input_index = self.add_input(file_path)
        return f"[{input_index}:{stream_type}]"

    def add_node(self, node):
        """Adds a FilterNode to the graph."""
        self.nodes.append(node)
        return node

    def connect(self, from_node, to_node, from_pin_idx=0, to_pin_idx=0):
        """Connects the output of one node to the input of another."""
        if from_pin_idx >= len(from_node.output_pins):
            raise ValueError(f"Source node '{from_node.name}' has no output pin at index {from_pin_idx}")
        if to_pin_idx >= len(to_node.input_pins):
            raise ValueError(f"Target node '{to_node.name}' has no input pin at index {to_pin_idx}")
        to_node.input_pins[to_pin_idx] = from_node.output_pins[from_pin_idx]

    def to_string(self):
        """Serializes the entire graph into a single string for FFmpeg."""
        logger = logging.getLogger("Advanced_Video_Editor")
        full_graph_str = ";".join(str(node) for node in self.nodes)
        logger.debug(f"[FILTER_GRAPH] Full serialized graph: {full_graph_str}")
        return full_graph_str
    @property
    def inputs(self):
        return self._inputs