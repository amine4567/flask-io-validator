FROM python:3.7

# Install python requirements
COPY requirements-combined.txt requirements-combined.txt
RUN pip install -r requirements-combined.txt

# Terminal autocompletion
RUN curl https://raw.githubusercontent.com/git/git/master/contrib/completion/git-completion.bash -o ~/.git-completion.bash
RUN inv --print-completion-script bash > ~/.invoke-completion.sh

# Custom bashrc
COPY .devcontainer/.bashrc_custom /root/.bashrc

# Some tools
RUN apt update &&\
    apt install -y tig nano