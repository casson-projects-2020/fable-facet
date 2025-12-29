# Security Considerations and Code Analysis
This is a tool for developers, so we consider that you can analyse the code in this repo to see that our claims about security are true.

However, to help in this task, here are the main security concerns and the code analysis related to them.

## 1 - Gemini API Key never crosses your GCP account boundary
We ask you to paste an API key created for Gemini. The interface that you will be seen when we request that can be found in this repo at /templates/index.html. 

The interface is shown using Google Cloud Shell web preview, running inside the environment of your GCP account. It uses a Python Flask server running on the 
same VM Cloud Shell uses. The code for the server can be found in this repo at /tutorial.py.

The API key is passed via JavaScript to the Flask server. You can see that on index.html:

<pre><code>
                const response = await fetch( './validate_key', 
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: elem( "gemini_key" ).textContent })
                });
</code></pre>

The python code in tutorial.py will validate the key:

<pre><code>
    try:
        client = genai.Client( api_key = key )
        models = client.models.list()

        env[ "GEMINI_KEY" ] = key

        return "ok", 200

    except Exception as e:
        return "Invalid key", 401
</code></pre>

Notice that the key, if valid, is set as an environment variable. In this way it can be used by Terraform to create
a cloud function v2 in your GCP account. Apart from the bucket with Terraform data (and the source code for the function,
that you can see in this repo in /function_code/main.py), this is the only resource created. You can
see the API key being used by Terraform in /yfc_install.sh:

<pre><code>
terraform apply -auto-approve -var="project_id=${PROJECT_ID}" -var="region=${REGION}" -var="infra_bucket=${BUCKET_NAME}" \
    -var="token=${TOKEN}" -var="api_key=${GEMINI_KEY}"
</code></pre>

And finally you can see how Terraform uses the API Key in main.tf:


