# Security Considerations and Code Analysis
This is a tool for developers, so we consider that you can analyse the code in this repo to see that our claims about security are true.

However, to help in this task, here are the main security concerns and the code analysis related to them.

## 1 - Gemini API Key never crosses your GCP account boundary
We ask you to paste an API key created for Gemini. The interface that you will be seen when we request that can be found in this repo at /templates/index.html. 

The interface is shown using Google Cloud Shell web preview, running inside the environment of your GCP account. It uses a Python Flask server running on the 
same VM Cloud Shell uses. The code for the server can be found in this repo at /tutorial.py.

The API key is passed via JavaScript to the Flask server. You can see that on index.html:

<code>
                const response = await fetch( './validate_key', 
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: elem( "gemini_key" ).textContent })
                });
</code>

The python code in tutorial.py will validate the key
