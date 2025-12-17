# Installing Your-Fable-Cloud

Wellcome! Let's prepare you Google Cloud Platform (GCP) Account so you can use your Gemini API free calls to generate stories.

## Step1: Select or Create a Project
To start you need an active project (a project in GCP is a workspace used to group resources).

<walkthrough-project-setup></walkthrough-project-setup>

If you don't see any project in the list above, click on "create a new project" . You can choose any name, like "Fable Facet", or any other. You can also install on any project if you already have one.

If you create a new one, close the tab afterwards, return to this tutorial and select your newly created project above.

### Configure the terminal to use the project
Click to copy this code to the terminal:

```bash
gcloud config set project {{project-id}}

## Step2: Run the installer
### Click below or copy-paste the command on the terminal:

```bash
chmod +x entrypoint.sh && ./entrypoint.sh
