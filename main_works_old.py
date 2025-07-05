"""This application is for a thesis project that will be used to automatically generate stories based on two inputs
The idea is to give 2 inputs which is the starting passage and end passage and then let the program, using llm, to subidive the story
into a deeper passage where the player needs to choose two routes.

Example:
    Input: Route Start
    Input: Route End

    1 - 2

    Output:
        1 - A - B - D - 2
              - C /

    This will generate a Dictionary with the story, where it'll have a start and finish and from there, A to ZZZ

"""
import networkx as nx
import matplotlib.pyplot as plt

from collections import deque

"""Main Class"""


def number_to_letters(n):
    result = ""
    while n >= 0:
        result = chr(n % 26 + ord('A')) + result
        n = n // 26 - 1
    return result


class StorySpliter:
    """Main init, will be used to initialize the class with the necessary parameters"""
    def __init__(self):
        #This will be used for the graph
        self.graph = nx.DiGraph()

        #This function will display the allowed subdividing edges
        self.allowSubdivide = []

        #This is the root node, the whole graph will consist on this node
        self.rootnode = None

        #Layer list, it'll help with the Y shenanigans
        self.layers = {}

        #Layer count to keep track of the layers
        self.layer = 1

        # This will store each text giving the "letter" and then it'll provide the text, this will be used for the graph
        self.texts = {}

        # This will store the position of each node that will be used in the DRAW Function
        self.pos = {}

        #This will be used to generate the letter names based on the function number_to_letters
        self.counter = 0

    """This function will add a new node to the graph, it'll get a new letter based on the counter and given the text from the user, if the text doesnt' exist just create some dummy text"""
    def _new_node(self, node_x, node_y, text = None) -> str:
        name = number_to_letters(self.counter)
        self.counter += 1

        if text is None:
            self.texts[name] = f"Dummy text for node {name}"
        else:
            self.texts[name] = f"{text}"

        self.pos[name] = (node_x, node_y)

        return name

    """This function will add a connecting between two nodes say for an example node 1 and 2 makes 1 - 2, This function will probably be used only once to create the initial graph,"""
    def initial_node_creation(self, from_node, from_text, to_node, to_text):
        #adds an edge to the main graph
        self.graph.add_edge(from_node, to_node)

        self.rootnode = from_node
        #The graph will start with nodes in (X = 0.5 and Y = -1) and (X = 0.5 and Y = -1) #MIGHT CHANGE LATER
        self.pos[from_node] = (0.5, 0)
        self.pos[to_node] = (0.5, -1)

        self.layers[self.layer] = from_node
        self.layer += 1
        self.layers[self.layer] = to_node

        #add the text to the nodes (Will be used when hovering over a certain node)
        self.texts[from_node] = f"{from_text}"
        self.texts[to_node] = f"{to_text}"

    """This function will contact the llm and then generate the given  """
    # TODO: Make this function later!

    def _getllmText(self, start, end) -> dict:
        to_return = {}

        return to_return

    """This function will organize the Y spacing between nodes"""

    def recalculate_layers(self, root):
        """Recalculate Y layers from the root node using BFS (longest path wins)"""
        # Root is always layer 0
        self.layers = {root: 0}

        #visited = set()
        queue = deque([root])
        while queue:
            current = queue.popleft()
            current_layer = self.layers[current]

            for neighbor in self.graph.successors(current):
                proposed_layer = current_layer + 1
                if neighbor not in self.layers or proposed_layer > self.layers[neighbor]:
                    self.layers[neighbor] = proposed_layer
                    queue.append(neighbor)

        # Update positions based on layers
        for node, layer in self.layers.items():
            x = self.pos[node][0]  # keep current x
            y = -layer * 1.0  # e.g., spacing 1.0 per layer
            self.pos[node] = (x, y)


    """With the help of LLM this will subdivide the given start and end node. In theory what will happen is, we'll use the power of llm to generate the needed nodes"""
    def subdivide(self, start, end):
        #giving the start and end node we can subdivide the passage into 6 nodes (including start and end)
        #creating the configuration start - A - B/C - D - end
        #then add the passages to the main Story dictionary

        #First very the edge exists, if we are going to subdivide one edge we need to make sure it exists a connection
        if not self.graph.has_edge(start, end):
            print(f"No direct edge from {start} to {end} found.")
            return

        #if (start, end) not in self.allowSubdivide:
        #    print(f"Not allowed subdivided edges, allowed subdivision: {self.allowSubdivide}")
        #    return

        # The connection exists now we remove that edge
        self.graph.remove_edge(start, end)

        """Now create intermediate nodes from the algorithm
        since We're following the structure:
            1
            |
            A
           / \
          B   C
           \ /
            D
            |
            2
        we want to keep this structure within our algorithm
        """

        # Here will be a function that will send to the llm the needed information to receive the text subdidivided (Probably will use a thread But for now its just dummy text)

        # TODO: finish this function and then integrate with it
        #llmText = self.getLLmText(start, end)

        # TODO: once the getllmtext function is done add the text in the right way in the _new_node

        start_node_pos = self.pos[start]
        end_node_pos = self.pos[end]

        xPos = start_node_pos[0]

        node_spacing = 0.25

        if start_node_pos[0] < 0.5:
            xPos = start_node_pos[0] - 0.1
        elif start_node_pos[0] > 0.5:
            xPos = start_node_pos[0] + 0.1

        a = self._new_node(node_x = xPos, node_y = start_node_pos[1] - node_spacing)
        b = self._new_node(node_x = xPos - node_spacing, node_y = start_node_pos[1] - node_spacing * 2)
        c = self._new_node(node_x = xPos + node_spacing, node_y = start_node_pos[1] - node_spacing * 2)
        d = self._new_node(node_x = xPos, node_y = start_node_pos[1] - node_spacing * 3)
        #self.pos[end] = (end_node_pos[0], end_node_pos[1] - node_spacing)

        #print(self.pos[end][1])
        #if self.pos[end][1] < self.pos[number_to_letters(1)][1]:
        #    print("this fot here")
        #    self.pos[number_to_letters(1)] = (self.pos[number_to_letters(1)][0], self.pos[end][1] - node_spacing * 4)



        # The nodes have been created, now let's create the edges
        self.graph.add_edge(start, a)
        self.graph.add_edge(a, b)
        self.graph.add_edge(a, c)
        self.graph.add_edge(b, d)
        self.graph.add_edge(c, d)
        self.graph.add_edge(d, end)

        # Don't manually adjust Y Anymore
        self.recalculate_layers(self.rootnode)

        print(f"Subdivided {start} -> {end} into {start} → {a} → {b}/{c} → {d} → {end}")


    """This function will draw the graph in a way that can be visualized by the user. We will use matplot """
    def draw(self):
        plt.figure(figsize=(8, 8))
        nx.draw(self.graph, pos=self.pos,
                with_labels=True,
                width=2,
                node_color='skyblue',
                node_size=1000,
                font_size=12,
                font_weight='bold',
                arrows=True)
        plt.title("Story Graph")
        plt.axis('off')
        plt.margins(0.2)
        plt.show()


"""The main function, When the program is executed this function will be called"""
if __name__ == "__main__":
    story = StorySpliter()
    exit_the_app = False

    story.initial_node_creation(from_node="1", from_text="Just a simple Text", to_node="2", to_text="Just another simple text")
    story.subdivide("1", "2")
    story.subdivide("B", "D")
    story.subdivide("C", "D")
    story.subdivide("K", "L")
    story.subdivide("O", "P")
    story.subdivide("F", "H")
    story.subdivide("L", "D")

    story.draw()

    #while not exit_the_app:
    #    pass


