import json
import re
import sys
import networkx as nx
from PyQt6.QtCore import QThread, Qt, QTimer, QPoint
from PyQt6.QtGui import QTextCursor, QMovie, QCursor
from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from collections import deque, defaultdict
from numpy import array, clip, dot, sqrt, hypot
import ollama

from mainUI import Ui_StoryXpander

from LLM_worker import *
from FinalVars import *
from support_functions import *
from support_dialogs import *


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        #Create the UI
        self.ui = Ui_StoryXpander()
        self.ui.setupUi(self)

        self.setFixedSize(FIXED_WIDTH,FIXED_HEIGHT)

        # This will be used for the graph
        self.graph = nx.DiGraph()

        # This is going to be used if its the first draw this does
        self.first_draw = True

        # This will be used for the expantion to reset the viewport
        self.expand = False

        #This will be used for the highlighted edge
        self.highlight_edge = []

        #this will be used for the possible expandable edges:
        self.expandable_edges = []

        #this will be used to start the story once you import this to Twine
        self.starting_node = None


        #This will be used for the little book animation once the user subdivides
        self.spinner = QLabel(self)
        self.spinner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.spinner.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.spinner.setStyleSheet("Background: transparent;")

        self.movie = QMovie("Book.gif")
        self.spinner.setMovie(self.movie)
        self.spinner.setVisible(False)

        #This wil lbe used for the canvas and replace the QFrame we've set up previously
        self.canvas = FigureCanvas(Figure(figsize=(8,8)))

        #Add commands for the canvas, like pan, zoom in/out and clicking
        #Will be userd for the dragging
        self.drag_start = None

        #Will be used for the current selected node
        self.current_selected_node = None

        #This add the Graph widget to the QFrame place without any margins
        self.layout_graph = QVBoxLayout(self.ui.nodes_frames)
        self.layout_graph.setContentsMargins(0,0,0,0)
        #self.layout_graph.addWidget(self.toolbar)
        self.layout_graph.addWidget(self.canvas)

        #this gives Axes to draw on
        self.ax = self.canvas.figure.add_subplot(111)

        # This is the root node, the whole graph will consist on this node
        self.rootnode = None

        #This is the last node, the graph will end on this node
        self.endnode = None

        #This is going to be used for the selected edge
        self.current_selected_edge = None

        # Layer list, it'll help with the Y shenanigans
        self.layers = {}

        # This will store each text giving the "letter" and then it'll provide the text, this will be used for the graph
        self.texts = {}

        #This dict will be used to keep the original text from the subdivision nodes.
        self.texts_originals = {}

        # This will store the position of each node that will be used in the DRAW Function
        self.pos = {}

        #For comparison on the mouse clicks, it'll help prevent unusual behavior
        self.mouse_down_pos = None
        self.mouse_up_pos = None

        # This will be used to generate the letter names based on the function number_to_letters
        self.counter = 0

        self.initial_node_creation(from_node="1",
                                   from_text=f"\"Alright! I got this, I found a new cave that's not in my maps, Adventure awaits!\" "
                                             f"said Lyara as she entered the cave, ready to explore the unknowness of the cave and bring"
                                             f" with her knowledge and treasure.She already imagines herself back in the guild showing of"
                                             f" her new discoveries and treasures, she would be the talk of the town! \"I'll show Bardus that I am a worthy"
                                             f" element in their guild!\"- Lyara said as she moved forward towards some stairs leading down.",
                                   to_node="2",

                                   to_text=f"After Climbing a set of stairs Lyara finds herself at where she was first when she started descending the cave stairs"
                                           f"\"This was incredible\" Said Lyara as she starts running towards town ready to tell the tales of her adventure"
                                           f"in the unknown cave. \"I'm sure they will name the cave my name after hearing my tales!\" Thought Lyara\n"
                                           f"THE END. ")




        #The logic of the buttons and mouse events
        self.ui.btn_expand.clicked.connect(self.handle_expand_button)

        self.ui.btn_export.clicked.connect(self.export_to_twine)

        #For when the user clicks on an item from the list
        self.ui.expand_nodes_list.itemClicked.connect(self.on_item_selected)

        #This is for the zoom in and zoom out
        self.canvas.mpl_connect("scroll_event", self.zoom_in_canvas)

        #This is for when the user clicks with both left click or right click
        self.canvas.mpl_connect("button_press_event", self.on_press_canvas)

        #This is for when the user moves the mouse on the canvas
        self.canvas.mpl_connect("motion_notify_event", self.on_motion_canvas)

        #This is for when the user relases the mouse button
        self.canvas.mpl_connect("button_release_event", self.on_release_canvas)

        #Since we want to track the mouse position all the time once the user clicks on the button to expando we'll keep a timer
        self.mouse_tracker_time = QTimer(self)
        self.mouse_tracker_time.timeout.connect(self.update_loading_icon_position)

        #This just draws the graph, This is only being called here because its the start of the program
        self.draw()

    """This function will add a new node to the graph, it'll get a new letter based on the counter and given the text from the user, if the text doesnt' exist just create some dummy text"""
    def _new_node(self, node_x, node_y, text = None, name_node = None) -> str:
        if name_node is None:
            name = number_to_letters(self.counter)
            self.counter += 1
        else:
            name = name_node

        if text is None:
            self.texts[name] = f"Dummy text for node {name}"
        else:
            self.texts[name] = f"{text}"

        self.pos[name] = (node_x, node_y)

        return name

    """This function will add a connecting between two nodes say for an example node 1 and 2 makes 1 - 2, This function will probably be used only once to create the initial graph,"""

    def initial_node_creation(self, from_node, from_text, to_node, to_text):
        # adds an edge to the main graph
        self.graph.add_edge(from_node, to_node)

        self.rootnode = from_node
        self.endnode = to_node
        # The graph will start with nodes in (X = 0.5 and Y = -1) and (X = 0.5 and Y = -1) #MIGHT CHANGE LATER
        self.pos[from_node] = (0.5, 0)
        self.pos[to_node] = (0.5, -1)

        # add the text to the nodes (Will be used when clicked over)
        self.texts[from_node] = f"{from_text}"
        self.texts[to_node] = f"{to_text}"

        self.add_text_to_information_box(f"Created node {from_node} to node {to_node}")
        self.ui.expand_nodes_list.addItem(f"{from_node}->{to_node}")

        self.expandable_edges.append((from_node, to_node))

        self.ui.lbl_counter.setText(str(len(self.graph.nodes)))



    """This function will contact the llm and then generate the given Text """

    def getLLmText(self, start, end):
        to_return = {}
        text_from_llm = ollama.generate(model='eldoria-story',
                                        prompt=f"Node 1: {self.texts[start]} Node 2: {self.texts[end]}")

        text_from_llm = text_from_llm["response"]

        #THIS IS WHY WE CAN'T HAVE NICE THINGS
        #because the llm is unreliable we need to make sure things are returned in the right form:
        # First let's strip Markdown code blocks: ```json\n...\n``` or ```\n...\n```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text_from_llm, re.DOTALL)
        json_str = ""
        if match:
            json_str = match.group(1)
        else:
            #This is actually pure json
            json_str = text_from_llm.strip()

        #Before parsing the Text might have some issues with the texts so let's Sanitize this before we all go mad here

        #replace smart quotes with normal quotes
        json_str = json_str.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")

        # Strip any trailing commas or excessive whitespace
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*\]", "]", json_str)

        #Next let's try parsing this and if there's an error we'll catch it:
        try:
            to_return = json.loads(json_str)
        except json.JSONDecodeError:
            return ERROR_JSON_PARSING

        #Ok After parsing sometimes this LLM forgets that 4 IS NOT 6 or 5 IS NOT 6 soo we need to make sure that the amount of keys returned is exactly 6!
        #Since we're at it why not just add another secure verification just for the kicks of it:
        if not isinstance(to_return, dict):
            return ERROR_NOT_DICT

        # Now we'll check if the key are exactly as that final variable we created up at the top
        if set(to_return.keys()) != EXPECTED_LLM_KEYS:
            #There's a chance that the keys don't match, so we'll check if the keys exist on the expected keys, if they don't then return the error
            #print(f"keys got: {to_return.keys()}")
            if not EXPECTED_LLM_KEYS.issubset(to_return.keys()):
                return ERROR_NUMBER_KEYS

        #Alright after all those verifications just return the dictionary
        return to_return

    def recalculate_layers(self, root):

        # Root is always layer 0
        self.layers = {root: 0}

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
        
        #If there's any node on X on top of each let's move them a bit to the left and the other to the right
        shift_amount = 0.1
        nodes = list(self.pos.items())

        for i in range(len(nodes)):
            node_i, (x_i, y_i) = nodes[i]

            for j in range(i + 1, len(nodes)):
                node_j, (x_j, y_j) = nodes[j]
                #if same X and same Y
                if abs(x_i - x_j) < 1e-5 and abs(y_i - y_j) < 1e-5:
                    self.pos[node_i] = (x_i - shift_amount, y_i)
                    self.pos[node_j] = (x_j + shift_amount, y_j)

                    x_i -= shift_amount
                    x_j += shift_amount

        #Debug purposes
        """
        print("Node positions:")
        for node, (x, y) in self.pos.items():
            print(f"{node}: x={x:.2f}, y={y:.2f}")
        """

    """With the help of LLM this will subdivide the given start and end node. In theory what will happen is, we'll use the power of llm to generate the needed nodes"""

    def subdivide(self, start, end, llmText):
        """
        giving the start and end node we can subdivide the passage into 6 nodes (including start and end)
        creating the configuration start - A - B/C - D - end
        then add the passages to the main Story dictionary

        Now create intermediate nodes from the algorithm
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

        text_a = llmText['A']
        text_b = llmText["B"]
        text_c = llmText["C"]
        text_d = llmText["D"]

        start_node_pos = self.pos[start]

        xPos = start_node_pos[0]

        node_spacing = 0.5

        if start_node_pos[0] < 0.5:
            xPos = start_node_pos[0] - 0.5
        elif start_node_pos[0] > 0.5:
            xPos = start_node_pos[0] + 0.5

        a = self._new_node(node_x=xPos, node_y=start_node_pos[1] - node_spacing, text=text_a)
        b = self._new_node(node_x=xPos - node_spacing, node_y=start_node_pos[1] - node_spacing * 2, text=text_b)
        c = self._new_node(node_x=xPos + node_spacing, node_y=start_node_pos[1] - node_spacing * 2, text=text_c)
        d = self._new_node(node_x=xPos, node_y=start_node_pos[1] - node_spacing * 3, text= text_d)

        #ADD The succession nodes to the text list
        self.texts[f"{a}_{b}"] = llmText["A_B"]
        self.texts[f"{a}_{c}"] = llmText["A_C"]

        #self.texts_originals[a] = llmText["A"]

        # The nodes have been created, now let's create the edges
        self.graph.add_edge(start, a)
        self.graph.add_edge(a, b)
        self.graph.add_edge(a, c)
        self.graph.add_edge(b, d)
        self.graph.add_edge(c, d)
        self.graph.add_edge(d, end)

        # Don't manually adjust X/Y Anymore
        self.recalculate_layers(self.rootnode)

        #This will add the information to the information box
        self.add_text_to_information_box(f"Subdivided {start} -> {end} into {start} → {a} → {b}/{c} → {d} → {end}")

        #Add the allowed nodes to the list of nodes to expand
        self.ui.expand_nodes_list.addItem(f"{b}->{d}")
        self.ui.expand_nodes_list.addItem(f"{c}->{d}")

        self.expandable_edges.append((b,d))
        self.expandable_edges.append((c,d))

        # The connection exists now we remove that edge
        self.graph.remove_edge(start, end)
        #Update the number of nodes
        self.ui.lbl_counter.setText(str(len(self.graph.nodes)))

        self.draw()

        return True

    """This function will draw the graph in a way that can be visualized by the user. We will use matplot """

    def draw(self):

        # Save current view limits to keep things as they are
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        #This clears the previous plot
        self.ax.clear()

        #Draw the graph with the given Axes

        node_colors = []
        for node in self.graph.nodes:
            if node == self.current_selected_node:
                node_colors.append(NODE_SELECT)
            elif node == self.starting_node:
                node_colors.append(NODE_START_POSITION)
            elif node == "1" or node == "2":
                node_colors.append(NODE_LOCKED)
            else:
                node_colors.append(NODE_DEFAULT) #This is default color

        edge_colors = []

        for u, v in self.graph.edges():
            if (u, v) in self.highlight_edge or (v, u) in self.highlight_edge:
                edge_colors.append(EDGE_HIGHLIGHT)

            elif (u,v) in self.expandable_edges or (v,u) in self.expandable_edges:
                edge_colors.append(EDGE_EXPANDABLE)

            else:
                edge_colors.append(EDGE_NORMAL)

        nx.draw(
            self.graph,
            pos=self.pos,
            ax=self.ax,
            with_labels=True,
            width=3,
            node_color=node_colors,
            edge_color = edge_colors,
            node_size=1500,
            font_size=14,
            font_weight='bold',
            arrows=True
        )

        #self.ax.set_title("Story Graph")
        self.ax.set_axis_off()

        if self.first_draw:
            self.first_draw = False
            self.canvas.draw_idle()
            return

        if self.expand:
            self.expand = False
            self.ax.relim()
            self.ax.autoscale_view()

        else:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)

        self.canvas.draw_idle()


    #Complementary for the Draw Function:
    def is_within_bounds(self, xlim, ylim):
        x_vals = [pos[0] for pos in self.pos.values()]
        y_vals = [pos[1] for pos in self.pos.values()]

        margin = 0.4  # 20% buffer
        return (
                min(x_vals) > xlim[0] - margin and max(x_vals) < xlim[1] + margin and
                min(y_vals) > ylim[0] - margin and max(y_vals) < ylim[1] + margin
        )

    #This function is just to make my life easier, just in case I need to modify the way I insert the text later >_>
    def add_text_to_information_box(self, text):
        pos_init = QTextCursor(self.ui.information_box.document())
        pos_init.setPosition(0)
        self.ui.information_box.setTextCursor(pos_init)
        self.ui.information_box.insertPlainText(f"{text}\n")

    #Function for when the user clicks on a item from the list
    def on_item_selected(self, item):
        selected_text = item.text()
        if "->" in selected_text:
            parts = selected_text.split("->")
        else:
            return

        self.highlight_edge = [(parts[0].strip(),parts[1].strip())]
        self.current_selected_edge = selected_text
        self.draw()


    #This function will be called once the user clicks the button to expand
    def handle_expand_button(self):
        selected_items = self.ui.expand_nodes_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(
                self,
                "No Path Selected!",
                "Please select a Path from the list on the right to expanding."
            )
            return

        #Select the node
        selected_item = selected_items[0]
        node_name = selected_item.text()

        #Gives the first and the second node
        nodes_split = node_name.split("->")

        #This is going to be for the thread when the user clicks on the button
        self.thread = QThread()
        self.worker = SubDivideWorker(nodes_split[0], nodes_split[1], self.getLLmText)
        self.worker.moveToThread(self.thread)

        self.set_buttons_toggle(False)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_subdivide_finished)
        self.worker.error.connect(self.on_subdivide_error)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.thread.deleteLater)
        self.worker.done.connect(self.worker.deleteLater)
        self.worker.done.connect(self.done_subdivide_thread)

        self.add_text_to_information_box("-------------------------------------------------")
        self.add_text_to_information_box(f"Expanding Path {node_name}")
        self.add_text_to_information_box(f"Please Wait a bit")

        #Starting the spinner
        self.movie.start()
        self.spinner.show()
        self.mouse_tracker_time.start(30) #every 30 miliseconds

        self.thread.start()

    def on_subdivide_finished(self, start, end, llm_text):
        # this was success so inject pre-generated text into subivided logic
        self.expand = True
        self.subdivide(start, end, llm_text)

        selected_item = self.ui.expand_nodes_list.selectedItems()[0]
        row = self.ui.expand_nodes_list.row(selected_item)

        # Remove selected item from the list
        self.ui.expand_nodes_list.takeItem(row)

        # clear the selection just to prevent some unusual shenanigans
        self.ui.expand_nodes_list.clearSelection()

    def on_subdivide_error(self, int_error):
        if int_error is ERROR_JSON_PARSING:
            # Json Parsing error, therefore there was an error.
            self.add_text_to_information_box(f"Json parsing error!")

        if int_error is ERROR_NOT_DICT:
            # Its empty, therefore there was an error.
            self.add_text_to_information_box(f"Result Isn't a Dictionary!")

        if int_error is ERROR_NUMBER_KEYS:
            # The keys don't match! therefore there was an error.
            self.add_text_to_information_box(f"Resulted Keys Aren't the same!")

        self.add_text_to_information_box(f"Trying Again!")
        QTimer.singleShot(0, self.handle_expand_button)

    def done_subdivide_thread(self):
        self.set_buttons_toggle(True)
        self.mouse_tracker_time.stop()
        self.movie.stop()
        self.spinner.hide()


    def set_buttons_toggle(self, state):
        self.ui.btn_expand.setEnabled(state)
        self.ui.btn_export.setEnabled(state)


    #CANVAS FUNCTIONS
    def zoom_in_canvas(self, event):
        base_scale = 1.2
        ax = self.ax

        #get current canvas limits
        x_lim = ax.get_xlim()
        y_lim = ax.get_ylim()

        #Get mouse position in axis coords

        x_data = event.xdata
        y_data = event.ydata

        if x_data is None and y_data is None:
            #the user is outside the canvas limits so just ignore it
            return

        #zoom factor
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale

        #New Limits
        new_x_lim = [
            x_data - (x_data - x_lim[0]) * scale_factor,
            x_data + (x_lim[1] - x_data) * scale_factor,
        ]

        new_y_lim = [
            y_data - (y_data - y_lim[0]) * scale_factor,
            y_data + (y_lim[1] - y_data) * scale_factor,
        ]

        ax.set_xlim(new_x_lim)
        ax.set_ylim(new_y_lim)
        self.canvas.draw_idle()

    def on_press_canvas(self, event):
        if event.button == 1 and event.inaxes:  # Left click inside the canvas axes
            self.drag_start = (event.x, event.y)
            self.mouse_down_pos = (event.x, event.y)

        elif event.button == 3 and event.inaxes: #Right click inside the canvas axes
            clicked_node = self.get_node_at_position(event)
            if clicked_node:
                self.starting_node = clicked_node
                self.draw()



    def on_motion_canvas(self,event):
        if self.drag_start and event.inaxes:
            #The user has the left button on the mouse down and its dragging inside the canvas
            #Which means there will be cake
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]

            ax = self.ax
            x_lim = ax.get_xlim()
            y_lim = ax.get_ylim()

            scale_x = (x_lim[1] - x_lim[0]) / self.canvas.width()
            scale_y = (y_lim[1] - y_lim[0]) / self.canvas.height()

            ax.set_xlim(x_lim[0] - dx * scale_x, x_lim[1] - dx * scale_x)
            ax.set_ylim(y_lim[0] - dy * scale_y, y_lim[1] - dy * scale_y)

            self.drag_start = (event.x, event.y)
            self.canvas.draw_idle()

    def on_release_canvas(self,event):
        self.drag_start = None

        self.mouse_up_pos = (event.x, event.y)
        if self.mouse_down_pos is None:
            return

        dx = self.mouse_up_pos[0] - self.mouse_down_pos[0]
        dy = self.mouse_up_pos[1] - self.mouse_down_pos[1]
        distance_square = dx**2 + dy**2

        if distance_square < 25: #Threshold change if i need it later:
            # It’s a click, not a drag
            clicked_node = self.get_node_at_position(event)
            if clicked_node:
                if getattr(event, 'dblclick', False):
                    if clicked_node not in {"1", "2"}:
                        curText = self.texts[clicked_node]
                        dialog = MultiLineTextDialog(
                            self,
                            title=f"Edit Node {clicked_node} Text",
                            label_text=f"Node{clicked_node} Text:",
                            default_text=curText
                        )

                        if dialog.exec():
                            self.texts[clicked_node] = dialog.getText()
                            self.add_text_to_information_box(f"Updated Node {clicked_node}'s text.")
                            self.draw()
                else:
                    if self.current_selected_node != clicked_node:
                        self.current_selected_node = clicked_node
                        self.add_text_to_information_box("-------------------------------------------------")
                        self.add_text_to_information_box(f"Node {clicked_node}: {self.texts[clicked_node]}")
                        self.draw()
            else:
                x_click, y_click = event.xdata, event.ydata
                min_dist = float('inf')
                closest_edge = None
                for edge in self.graph.edges:
                    src, dst = edge

                    if src in self.pos and dst in self.pos:
                        x1, y1 = self.pos[src]
                        x2, y2 = self.pos[dst]

                        dist = self.point_to_segment_distance(x_click, y_click, x1, y1, x2, y2)
                        # Lets do dynamic threshold and not by manual like we we're doing

                        edge_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                        dynamic_threshold = max(0.01 * edge_length, 0.002)  # 1% of edge length, but not smaller than 0.002
                        if dist < dynamic_threshold and dist < min_dist:
                            min_dist = dist
                            closest_edge = edge
                        # Start drag only if not on node

                if closest_edge:
                    edge_str = f"{closest_edge[0]}->{closest_edge[1]}"
                    for i in range(self.ui.expand_nodes_list.count()):
                        item = self.ui.expand_nodes_list.item(i)
                        if item.text() == edge_str:
                            if item.text() != self.current_selected_edge:
                                self.ui.expand_nodes_list.setCurrentRow(i)
                                self.add_text_to_information_box(f"Selected Path: {edge_str}")
                                self.on_item_selected(item)
                                self.current_selected_edge = item.text()
                                break


    def point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        #Vector from point 1 to point 2
        dx, dy = x2 - x1, y2 - y1

        if dx == dy == 0:
            #line segment is a point
            return hypot(px - x1, py - y1)

        #parameter t of the projection point on the segment
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return hypot(px - proj_x, py - proj_y)

    def get_node_at_position(self, event):
        #This function will return the closest node within a tolerance radius.
        if not hasattr(self, 'pos') or event.x is None or event.y is None:
            return None

        #Before we were trying with min_distance now let's just focus on pixel distance
        pixel_threshold = 25  # Adjust as needed (5–15 pixels is typical)

        closest_node = None
        closest_dist = float('inf')

        for node, (x,y) in self.pos.items():
            screen_x, screen_y = self.ax.transData.transform((x, y))
            dist = ((screen_x - event.x) ** 2 + (screen_y - event.y) ** 2) ** 0.5
            if dist < pixel_threshold and dist < closest_dist:
                closest_dist = dist
                closest_node = node

        return closest_node

    def update_loading_icon_position(self):
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)

        offset = QPoint(10, 10)
        self.spinner.move(local_pos + offset)

    def export_to_twine(self):
        lines = []
        #new_dict = copy.deepcopy(self.texts)
        #new_dict.update(self.texts_originals)

        lines.append(f":: StoryData\n"
                     f"{{\n"
                     f"\"format\":\"Harlowe\",\n"
                     f"\"format-version\":\"3.3.9\",\n"
                     f"\"zoom\":\"1\",\n"
                     f"\"start\":\"{self.starting_node}\"\n"
                     f"}}")

        for node in self.graph.nodes:
            title = str(node)
            text = self.texts.get(node,"[No Text]").strip()
            successors = list(self.graph.successors(node))

            #let's write the passage titles

            lines.append(f":: {title}")
            lines.append(text)

            for target in successors:
                link_key = f"{node}_{target}"
                link_text = self.texts.get(link_key)

                if link_text:
                    clean_text = link_text.strip().strip('"').strip("'")
                    lines.append(f"[[{clean_text}->{target}]]")

                else:
                    #fallback : just show default link
                    lines.append(f"[[Continue->{target}]]")
            lines.append("")

        with open("text.twee", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        QMessageBox.warning(
            self,
            "Complete!",
            "Export Successfully!."
        )
        return



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


