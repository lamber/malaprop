# damerau_levenshtein_channel.py

import codecs, unicodedata, random

class ErrorProbabilities():

    """
    """

    def __init__ (self, none, substitution, insertion, transposition, deletion):

        assert abs(1.0 - (none + substitution + insertion + transposition + deletion) < 0.000001)
        self.none = none
        self.substitution = substitution
        self.insertion = insertion
        self.transposition = transposition
        self.deletion = deletion

class DamerauLevenshteinChannel():

    """
    Holds up to one char in a queue, and processes incoming chars.
    """

    def __init__(self, random_number_generator, probabilities, symbol_set, output_method):
        
        self.random_number_generator = random_number_generator
        self.probabilities = probabilities
        self.symbol_set = symbol_set
        self.write = output_method
        self.queue = []
        self.stats = {'chars':0, 'subs':0, 'ins':0, 'dels':0, 'trans':0, 'strings':0, 'max_errors_per_string':0}

    def pop(self):

        try:
            result = self.queue.pop()
        except:
            result = None
        return result

    def push(self, char):

        result = self.pop()
        self.queue.append(char)
        assert len(self.queue) < 2, self.queue
        return result

    def get_substitute(self, char):

        char_index = self.symbol_set.index(char)
        return self.random_number_generator.choice(self.symbol_set[:char_index]+self.symbol_set[char_index+1:])

    def get_insert(self):

        return self.random_number_generator.choice(self.symbol_set)

    def flush(self):

        self.write(self.pop())

    def accept_char(self, char):

        if char is not None: 
            # Always leave unknown chars alone
            if char not in self.symbol_set:
                self.write(self.push(char))
                self.flush()
                return
            self.stats['chars'] += 1

        random_number = self.random_number_generator.random()

        if random_number < self.probabilities.none:
            self.write(self.push(char))

        elif random_number < self.probabilities.none + self.probabilities.substitution \
                and char is not None:
            self.stats['subs'] += 1
            self.write(self.push(self.get_substitute(char)))

        elif random_number < self.probabilities.none + self.probabilities.substitution + self.probabilities.insertion:
            self.stats['ins'] += 1
            self.write(self.push(self.get_insert()))
            self.write(self.push(char))

        elif random_number < self.probabilities.none + self.probabilities.substitution + self.probabilities.insertion + self.probabilities.deletion:
            if char is not None: self.stats['dels'] += 1
            self.write(self.pop()) # Dequeue in case of pending transpositions.
            
        else: # transposition
            pending = self.pop()
            if pending is not None and char is not None: self.stats['trans'] += 1
            self.push(char)
            self.write(self.push(pending))


    def accept_string(self, string):

        prior_errors = sum([self.stats[x] for x in ['subs', 'ins', 'dels', 'trans']])
        for i in range(len(string)):
            char = string[i]
            if i != 0 and char not in self.symbol_set:
                self.accept_char(None) # Possible insertion
                self.flush()
            self.accept_char(char)

        self.accept_char(None) # Possible insertion
        self.flush()
        self.stats['strings'] += 1
        current_errors = sum([self.stats[x] for x in ['subs', 'ins', 'dels', 'trans']])
        self.stats['max_errors_per_string'] = max(current_errors-prior_errors, self.stats['max_errors_per_string'])

