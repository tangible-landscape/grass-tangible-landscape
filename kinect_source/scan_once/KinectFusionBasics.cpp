//------------------------------------------------------------------------------
// <copyright file="KinectFusionBasics.cpp" company="Microsoft">
//     Copyright (c) Microsoft Corporation.  All rights reserved.
// </copyright>
//------------------------------------------------------------------------------

// System includes
#include "stdafx.h"
#include <string>
#include <strsafe.h>
#include <fstream>
#include <iostream>
#include <cstdio>
#include <algorithm>
#include <unordered_set>
#define _USE_MATH_DEFINES
#include <math.h>
#include <new>
#include <shellapi.h>


// Project includes
#include "resource.h"
#include "KinectFusionBasics.h"


bool cvtLPW2stdstring(std::string& s, const LPWSTR pw,
                      UINT codepage = CP_ACP)
{
    bool res = false;
    char* p = 0;
    int bsz;
    bsz = WideCharToMultiByte(codepage,
        0,
        pw,-1,
        0,0,
        0,0);
    if (bsz > 0) {
        p = new char[bsz];
        int rc = WideCharToMultiByte(codepage,
            0,
            pw,-1,
            p,bsz,
            0,0);
        if (rc != 0) {
            p[bsz-1] = 0;
            s = p;
            res = true;
        }
    }
    delete [] p;
    return res;
}

/// <summary>
/// Entry point for the application
/// </summary>
/// <param name="hInstance">handle to the application instance</param>
/// <param name="hPrevInstance">always 0</param>
/// <param name="lpCmdLine">command line arguments</param>
/// <param name="nCmdShow">whether to display minimized, maximized, or normally</param>
/// <returns>status</returns>
int APIENTRY wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPWSTR lpCmdLine, int nCmdShow)
{
    LPWSTR *szArglist;
	int nArgs = 0;
	szArglist = CommandLineToArgvW(GetCommandLineW(), &nArgs);

    if (nArgs != 5){
        return 1;
    }

    std::string program, fileName;

    cvtLPW2stdstring (program, szArglist[0]);
    cvtLPW2stdstring (fileName, szArglist[1]);
    int nFrames = _wtoi (szArglist[2]);
    double minZ = _wtof (szArglist[3]);
    double maxZ = _wtof (szArglist[4]);

    CKinectFusionBasics application(minZ, maxZ);

    application.Run(hInstance, nCmdShow, fileName, nFrames);
}



/// <summary>
/// Set Identity in a Matrix4
/// </summary>
/// <param name="mat">The matrix to set to identity</param>
void SetIdentityMatrix(Matrix4 &mat)
{
    mat.M11 = 1; mat.M12 = 0; mat.M13 = 0; mat.M14 = 0;
    mat.M21 = 0; mat.M22 = 1; mat.M23 = 0; mat.M24 = 0;
    mat.M31 = 0; mat.M32 = 0; mat.M33 = 1; mat.M34 = 0;
    mat.M41 = 0; mat.M42 = 0; mat.M43 = 0; mat.M44 = 1;
}

/// <summary>
/// Constructor
/// </summary>
CKinectFusionBasics::CKinectFusionBasics(double minZ, double maxZ) :
    m_pD2DFactory(nullptr),
    m_pDrawDepth(nullptr),
    m_pVolume(nullptr),
    m_pNuiSensor(nullptr),
    m_depthImageResolution(NUI_IMAGE_RESOLUTION_640x480),
    m_cDepthImagePixels(0),
    m_hNextDepthFrameEvent(INVALID_HANDLE_VALUE),
    m_pDepthStreamHandle(INVALID_HANDLE_VALUE),
    m_bNearMode(true),
    m_bMirrorDepthFrame(false),
    m_bTranslateResetPoseByMinDepthThreshold(true),
    m_bAutoResetReconstructionWhenLost(false),
    m_bAutoResetReconstructionOnTimeout(true),
    m_cLostFrameCounter(0),
    m_bTrackingFailed(false),
    m_cFrameCounter(0),
    m_fStartTime(0),
    m_pDepthImagePixelBuffer(nullptr),
    m_pDepthFloatImage(nullptr),
    m_pPointCloud(nullptr),
    m_pShadedSurface(nullptr),
    m_bInitializeError(false),
    m_depthFrameCount(0)
{
    // Get the depth frame size from the NUI_IMAGE_RESOLUTION enum
    // You can use NUI_IMAGE_RESOLUTION_640x480 or NUI_IMAGE_RESOLUTION_320x240 in this sample
    // Smaller resolutions will be faster in per-frame computations, but show less detail in reconstructions.
    DWORD width = 0, height = 0;
    NuiImageResolutionToSize(m_depthImageResolution, width, height);
    m_cDepthWidth = width;
    m_cDepthHeight = height;
    m_cDepthImagePixels = m_cDepthWidth*m_cDepthHeight;

    // create heap storage for depth pixel data in RGBX format
    m_pDepthRGBX = new BYTE[m_cDepthImagePixels*cBytesPerPixel];

    // Define a cubic Kinect Fusion reconstruction volume,
    // with the Kinect at the center of the front face and the volume directly in front of Kinect.
    m_reconstructionParams.voxelsPerMeter = 640;// 1000mm / 256vpm = ~3.9mm/voxel    
    m_reconstructionParams.voxelCountX = 512;   // 512 / 256vpm = 2m wide reconstruction
    m_reconstructionParams.voxelCountY = 512;   // Memory = 512*384*512 * 4bytes per voxel
    m_reconstructionParams.voxelCountZ = 512;   // This will require a GPU with at least 512MB

    // These parameters are for optionally clipping the input depth image 
    m_fMinDepthThreshold = minZ;//NUI_FUSION_DEFAULT_MINIMUM_DEPTH;   // min depth in meters
    m_fMaxDepthThreshold = maxZ; //NUI_FUSION_DEFAULT_MAXIMUM_DEPTH;    // max depth in meters

    // This parameter is the temporal averaging parameter for depth integration into the reconstruction
    m_cMaxIntegrationWeight = 500;//NUI_FUSION_DEFAULT_INTEGRATION_WEIGHT;	// Reasonable for static scenes

    // This parameter sets whether GPU or CPU processing is used. Note that the CPU will likely be 
    // too slow for real-time processing.
    m_processorType = NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_AMP;

    // If GPU processing is selected, we can choose the index of the device we would like to
    // use for processing by setting this zero-based index parameter. Note that setting -1 will cause
    // automatic selection of the most suitable device (specifically the DirectX11 compatible device 
    // with largest memory), which is useful in systems with multiple GPUs when only one reconstruction
    // volume is required. Note that the automatic choice will not load balance across multiple 
    // GPUs, hence users should manually select GPU indices when multiple reconstruction volumes 
    // are required, each on a separate device.
    m_deviceIndex = -1;    // automatically choose device index for processing

    SetIdentityMatrix(m_worldToCameraTransform);
    SetIdentityMatrix(m_defaultWorldToVolumeTransform);

    m_cLastDepthFrameTimeStamp.QuadPart = 0;
}

/// <summary>
/// Destructor
/// </summary>
CKinectFusionBasics::~CKinectFusionBasics()
{
    // Clean up Kinect Fusion
    SafeRelease(m_pVolume);

    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pShadedSurface);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pPointCloud);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDepthFloatImage);

    // Clean up Kinect
    if (m_pNuiSensor)
    {
        m_pNuiSensor->NuiShutdown();
        m_pNuiSensor->Release();
    }

    if (m_hNextDepthFrameEvent != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hNextDepthFrameEvent);
    }

    // clean up the depth pixel array
    SAFE_DELETE_ARRAY(m_pDepthImagePixelBuffer);

    // clean up Direct2D renderer
    SAFE_DELETE(m_pDrawDepth);

    // done with depth pixel data
    SAFE_DELETE_ARRAY(m_pDepthRGBX);

    // clean up Direct2D
    SafeRelease(m_pD2DFactory);
}

// TODO
bool myEquals (Vector3 i, Vector3 j) {
    return ((i.x==j.x) && (i.y == j.y) && (i.z == j.z));
}

bool myLess (Vector3 i, Vector3 j) {
    if (i.x < j.x)
        return true;
    else if (i.x == j.x)
        if ( i.y < j.y)
            return true;
        else if (i.y == j.y)
            if (i.z < j.z)
                return true;
            else
                return false;
        else
            return false;
    else
        return false;

}

/// <summary>
/// Creates the main window and begins processing
/// </summary>
/// <param name="hInstance">handle to the application instance</param>
/// <param name="nCmdShow">whether to display minimized, maximized, or normally</param>
int CKinectFusionBasics::Run(HINSTANCE hInstance, int nCmdShow, std::string fileName, int nFrames)
{
    MSG       msg = {0};
    WNDCLASS  wc;

    // Dialog custom window class
    ZeroMemory(&wc, sizeof(wc));
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.cbWndExtra    = DLGWINDOWEXTRA;
    wc.hInstance     = hInstance;
    wc.hCursor       = LoadCursorW(nullptr, IDC_ARROW);
    wc.hIcon         = LoadIconW(hInstance, MAKEINTRESOURCE(IDI_APP));
    wc.lpfnWndProc   = DefDlgProcW;
    wc.lpszClassName = L"KinectFusionBasicsAppDlgWndClass";

    if (!RegisterClassW(&wc))
    {
        return 0;
    }

    // Create main application window
    HWND hWndApp = CreateDialogParamW(
        hInstance,
        MAKEINTRESOURCE(IDD_APP),
        nullptr,
        (DLGPROC)CKinectFusionBasics::MessageRouter, 
        reinterpret_cast<LPARAM>(this));

    // Show window
    //ShowWindow(hWndApp, nCmdShow);

    const int eventCount = 1;
    HANDLE hEvents[eventCount];

    // Main message loop
    while (WM_QUIT != msg.message)
    {
        hEvents[0] = m_hNextDepthFrameEvent;

        // Check to see if we have either a message (by passing in QS_ALLINPUT)
        // Or a Kinect event (hEvents)
        // Update() will check for Kinect events individually, in case more than one are signalled
        DWORD dwEvent = MsgWaitForMultipleObjects(eventCount, hEvents, FALSE, INFINITE, QS_ALLINPUT);

        // Check if this is an event we're waiting on and not a timeout or message
        if (WAIT_OBJECT_0 == dwEvent)
        {
			if (m_depthFrameCount >= nFrames){
				INuiFusionMesh *mesh = nullptr;
				HRESULT hr = m_pVolume->CalculateMesh(1, &mesh);
				if (SUCCEEDED(hr)){
					//FILE *meshFile = NULL;
					//errno_t err = fopen_s(&meshFile, "C:\\\\Users\\akratoc\\TanGeoMS\\output\\test1.obj", "wt");
					// Could not open file for writing - return
					//if (0 != err || NULL == meshFile)
					//{
					//	printf("NO FILE XXXX");fflush(stdout);
					//}
					int numVertices = mesh->VertexCount();
					const Vector3 *vertices = NULL;
					hr = mesh->GetVertices(&vertices);
                    std::vector<Vector3> copyVector(vertices, vertices + numVertices);
                    std::sort (copyVector.begin(), copyVector.end(), myLess);
                    std::vector<Vector3>::const_iterator newit;
                    newit = std::unique (copyVector.begin(), copyVector.end(), myEquals);

                    // create lock file
                    FILE *lockFile = NULL;
                    std::string lockFileName = fileName + "lock";
                    fopen_s(&lockFile, lockFileName.c_str(), "wt");
                    fclose(lockFile);
                    std::ofstream stream( fileName, std::ofstream::out);
                    bool isopen = stream.is_open();
                    for (std::vector<Vector3>::const_iterator it = copyVector.begin(); it != newit;++it){
						Vector3 vertex = *it;
						//vertex.y = -vertex.y;
						//vertex.z = -vertex.z;
                        //stream << "a" << std::endl;
                        stream << vertex.x << ' ' << -vertex.y << ' ' << -vertex.z << std::endl;

						//std::string vertexString = to_string(vertex.x) + " " + to_string(vertex.y) + " " + to_string(vertex.z) + "\n" ;
                        //fwrite(vertexString.c_str(), sizeof(char), vertexString.length(), meshFile);
					}
                    

                    //for (std::unordered_set<std::string>::iterator it=unique_vertices.begin(); it!=unique_vertices.end(); ++it){
                    //    fwrite((*it).c_str(), sizeof(char), (*it).length(), meshFile);
                    //}
                    stream.close();
					//fflush(meshFile);
					//fclose(meshFile);
                    std::remove(lockFileName.c_str());

					SafeRelease(mesh);
				}
				PostQuitMessage(0);
			}
			else {
				Update();
			}
        }

        if (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE))
        {
            // If a dialog message will be taken care of by the dialog proc
            if ((hWndApp != nullptr) && IsDialogMessageW(hWndApp, &msg))
            {
                continue;
            }

            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }

    return static_cast<int>(msg.wParam);
}

/// <summary>
/// Main processing function
/// </summary>
void CKinectFusionBasics::Update()
{
    if (nullptr == m_pNuiSensor)
    {
        return;
    }

    if ( WAIT_OBJECT_0 == WaitForSingleObject(m_hNextDepthFrameEvent, 0) )
    {
        ProcessDepth();
    }
}

/// <summary>
/// Handles window messages, passes most to the class instance to handle
/// </summary>
/// <param name="hWnd">window message is for</param>
/// <param name="uMsg">message</param>
/// <param name="wParam">message data</param>
/// <param name="lParam">additional message data</param>
/// <returns>result of message processing</returns>
LRESULT CALLBACK CKinectFusionBasics::MessageRouter(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
    CKinectFusionBasics* pThis = nullptr;
    
    if (WM_INITDIALOG == uMsg)
    {
        pThis = reinterpret_cast<CKinectFusionBasics*>(lParam);
        SetWindowLongPtr(hWnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(pThis));
    }
    else
    {
        pThis = reinterpret_cast<CKinectFusionBasics*>(::GetWindowLongPtr(hWnd, GWLP_USERDATA));
    }

    if (pThis)
    {
        return pThis->DlgProc(hWnd, uMsg, wParam, lParam);
    }

    return 0;
}

/// <summary>
/// Handle windows messages for the class instance
/// </summary>
/// <param name="hWnd">window message is for</param>
/// <param name="uMsg">message</param>
/// <param name="wParam">message data</param>
/// <param name="lParam">additional message data</param>
/// <returns>result of message processing</returns>
LRESULT CALLBACK CKinectFusionBasics::DlgProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    switch (message)
    {
        case WM_INITDIALOG:
        {
            // Bind application window handle
            m_hWnd = hWnd;

            // Init Direct2D
            //D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &m_pD2DFactory);

            // Create and initialize a new Direct2D image renderer (take a look at ImageRenderer.h)
            // We'll use this to draw the data we receive from the Kinect to the screen
           /* m_pDrawDepth = new ImageRenderer();
            HRESULT hr = m_pDrawDepth->Initialize(GetDlgItem(m_hWnd, IDC_VIDEOVIEW), m_pD2DFactory, m_cDepthWidth, m_cDepthHeight, m_cDepthWidth * sizeof(int));
            if (FAILED(hr))
            {
                SetStatusMessage(L"Failed to initialize the Direct2D draw device.");
                m_bInitializeError = true;
            }*/

            // Look for a connected Kinect, and create it if found
            HRESULT hr = CreateFirstConnected();
            if (FAILED(hr))
            {
                m_bInitializeError = true;
            }

            if (!m_bInitializeError)
            {
                hr = InitializeKinectFusion();
                if(FAILED(hr))
                {
                    m_bInitializeError = true;
                }
            }
        }
        break;

        // If the title bar X is clicked, destroy app
        case WM_CLOSE:
            DestroyWindow(hWnd);
            break;

        case WM_DESTROY:
            // Quit the main message pump
            PostQuitMessage(0);
            break;

        // Handle button press
        case WM_COMMAND:
            // If it was for the near mode control and a clicked event, change near mode
            if (IDC_CHECK_NEARMODE == LOWORD(wParam) && BN_CLICKED == HIWORD(wParam))
            {
                // Toggle our internal state for near mode
                m_bNearMode = !m_bNearMode;

                if (nullptr != m_pNuiSensor)
                {
                    // Set near mode based on our internal state
                    m_pNuiSensor->NuiImageStreamSetImageFrameFlags(m_pDepthStreamHandle, m_bNearMode ? NUI_IMAGE_STREAM_FLAG_ENABLE_NEAR_MODE : 0);
                }
            }
            // If the reset reconstruction button was clicked, clear the volume 
            // and reset tracking parameters
            if (IDC_BUTTON_RESET_RECONSTRUCTION == LOWORD(wParam) && BN_CLICKED == HIWORD(wParam))
            {
                ResetReconstruction();
            }
            break;
    }

    return FALSE;
}

/// <summary>
/// Create the first connected Kinect found 
/// </summary>
/// <returns>indicates success or failure</returns>
HRESULT CKinectFusionBasics::CreateFirstConnected()
{
    INuiSensor * pNuiSensor;
    HRESULT hr;

    int iSensorCount = 0;
    hr = NuiGetSensorCount(&iSensorCount);
    if (FAILED(hr))
    {
        SetStatusMessage(L"No ready Kinect found!");
        return hr;
    }

    // Look at each Kinect sensor
    for (int i = 0; i < iSensorCount; ++i)
    {
        // Create the sensor so we can check status, if we can't create it, move on to the next
        hr = NuiCreateSensorByIndex(i, &pNuiSensor);
        if (FAILED(hr))
        {
            continue;
        }

        // Get the status of the sensor, and if connected, then we can initialize it
        hr = pNuiSensor->NuiStatus();
        if (S_OK == hr)
        {
            m_pNuiSensor = pNuiSensor;
            break;
        }

        // This sensor wasn't OK, so release it since we're not using it
        pNuiSensor->Release();
    }

    if (nullptr != m_pNuiSensor)
    {
        // Initialize the Kinect and specify that we'll be using depth
        hr = m_pNuiSensor->NuiInitialize(NUI_INITIALIZE_FLAG_USES_DEPTH); 
        if (SUCCEEDED(hr))
        {
            // Create an event that will be signaled when depth data is available
            m_hNextDepthFrameEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);

            // Open a depth image stream to receive depth frames
            hr = m_pNuiSensor->NuiImageStreamOpen(
                NUI_IMAGE_TYPE_DEPTH,
                m_depthImageResolution,
                0,
                2,
                m_hNextDepthFrameEvent,
                &m_pDepthStreamHandle);
        }

        if (m_bNearMode)
        {
            // Set near mode based on our internal state
            HRESULT nearHr = m_pNuiSensor->NuiImageStreamSetImageFrameFlags(m_pDepthStreamHandle, NUI_IMAGE_STREAM_FLAG_ENABLE_NEAR_MODE);
            if (SUCCEEDED(nearHr))
            {
                CheckDlgButton(m_hWnd, IDC_CHECK_NEARMODE, BST_CHECKED);
            }
            else
            {
                EnableWindow(GetDlgItem(m_hWnd, IDC_CHECK_NEARMODE), FALSE);
            }
        }
    }

    if (nullptr == m_pNuiSensor || FAILED(hr))
    {
        SetStatusMessage(L"No ready Kinect found!");
        return E_FAIL;
    }

    return hr;
}

/// <summary>
/// Initialize Kinect Fusion volume and images for processing
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT CKinectFusionBasics::InitializeKinectFusion()
{
    HRESULT hr = S_OK;

    // Check to ensure suitable DirectX11 compatible hardware exists before initializing Kinect Fusion
    WCHAR description[MAX_PATH];
    WCHAR instancePath[MAX_PATH];
    UINT memorySize = 0;

    if (FAILED(hr = NuiFusionGetDeviceInfo(
        m_processorType, 
        m_deviceIndex, 
        &description[0], 
        ARRAYSIZE(description), 
        &instancePath[0],
        ARRAYSIZE(instancePath), 
        &memorySize)))
    {
        if (hr ==  E_NUI_BADINDEX)
        {
            // This error code is returned either when the device index is out of range for the processor 
            // type or there is no DirectX11 capable device installed. As we set -1 (auto-select default) 
            // for the device index in the parameters, this indicates that there is no DirectX11 capable 
            // device. The options for users in this case are to either install a DirectX11 capable device
            // (see documentation for recommended GPUs) or to switch to non-real-time CPU based 
            // reconstruction by changing the processor type to NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_CPU.
            SetStatusMessage(L"No DirectX11 device detected, or invalid device index - Kinect Fusion requires a DirectX11 device for GPU-based reconstruction.");
        }
        else
        {
            SetStatusMessage(L"Failed in call to NuiFusionGetDeviceInfo.");
        }
        return hr;
    }

    // Create the Kinect Fusion Reconstruction Volume
    hr = NuiFusionCreateReconstruction(
        &m_reconstructionParams,
        m_processorType, m_deviceIndex,
        &m_worldToCameraTransform,
        &m_pVolume);

    if (FAILED(hr))
    {
        if (E_NUI_GPU_FAIL == hr)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Device %d not able to run Kinect Fusion, or error initializing.", m_deviceIndex);
            SetStatusMessage(buf);
        }
        else if (E_NUI_GPU_OUTOFMEMORY == hr)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Device %d out of memory error initializing reconstruction - try a smaller reconstruction volume.", m_deviceIndex);
            SetStatusMessage(buf);
        }
        else if (NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_CPU != m_processorType)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Failed to initialize Kinect Fusion reconstruction volume on device %d.", m_deviceIndex);
            SetStatusMessage(buf);
        }
        else
        {
            SetStatusMessage(L"Failed to initialize Kinect Fusion reconstruction volume on CPU.");
        }

        return hr;
    }

    // Save the default world to volume transformation to be optionally used in ResetReconstruction
    hr = m_pVolume->GetCurrentWorldToVolumeTransform(&m_defaultWorldToVolumeTransform);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Failed in call to GetCurrentWorldToVolumeTransform.");
        return hr;
    }

    if (m_bTranslateResetPoseByMinDepthThreshold)
    {
        // This call will set the world-volume transformation
        hr = ResetReconstruction();
        if (FAILED(hr))
        {
            return hr;
        }
    }

    // Frames generated from the depth input
    hr = NuiFusionCreateImageFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, m_cDepthWidth, m_cDepthHeight, nullptr, &m_pDepthFloatImage);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Failed to initialize Kinect Fusion image.");
        return hr;
    }

    // Create images to raycast the Reconstruction Volume
    hr = NuiFusionCreateImageFrame(NUI_FUSION_IMAGE_TYPE_POINT_CLOUD, m_cDepthWidth, m_cDepthHeight, nullptr, &m_pPointCloud);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Failed to initialize Kinect Fusion image.");
        return hr;
    }

    // Create images to raycast the Reconstruction Volume
    hr = NuiFusionCreateImageFrame(NUI_FUSION_IMAGE_TYPE_COLOR, m_cDepthWidth, m_cDepthHeight, nullptr, &m_pShadedSurface);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Failed to initialize Kinect Fusion image.");
        return hr;
    }

    m_pDepthImagePixelBuffer = new(std::nothrow) NUI_DEPTH_IMAGE_PIXEL[m_cDepthImagePixels];
    if (nullptr == m_pDepthImagePixelBuffer)
    {
        SetStatusMessage(L"Failed to initialize Kinect Fusion depth image pixel buffer.");
        return hr;
    }

    m_fStartTime = m_timer.AbsoluteTime();

    // Set an introductory message
    SetStatusMessage(
        L"Click ‘Near Mode’ to change sensor range, and ‘Reset Reconstruction’ to clear!");

    return hr;
}

/// <summary>
/// Copy the extended depth data out of a Kinect image frame
/// </summary>
/// <param name="imageFrame">The extended depth image frame to copy.</param>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT CKinectFusionBasics::CopyExtendedDepth(NUI_IMAGE_FRAME &imageFrame)
{
    HRESULT hr = S_OK;

    if (nullptr == m_pDepthImagePixelBuffer)
    {
        SetStatusMessage(L"Error depth image pixel buffer is nullptr.");
        return E_FAIL;
    }

    INuiFrameTexture *extendedDepthTex = nullptr;

    // Extract the extended depth in NUI_DEPTH_IMAGE_PIXEL format from the frame
    BOOL nearModeOperational = FALSE;
    hr = m_pNuiSensor->NuiImageFrameGetDepthImagePixelFrameTexture(m_pDepthStreamHandle, &imageFrame, &nearModeOperational, &extendedDepthTex);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Error getting extended depth texture.");
        return hr;
    }

    NUI_LOCKED_RECT extendedDepthLockedRect;

    // Lock the frame data to access the un-clamped NUI_DEPTH_IMAGE_PIXELs
    hr = extendedDepthTex->LockRect(0, &extendedDepthLockedRect, nullptr, 0);

    if (FAILED(hr) || extendedDepthLockedRect.Pitch == 0)
    {
        SetStatusMessage(L"Error getting extended depth texture pixels.");
        return hr;
    }

    // Copy the depth pixels so we can return the image frame
    errno_t err = memcpy_s(m_pDepthImagePixelBuffer, m_cDepthImagePixels * sizeof(NUI_DEPTH_IMAGE_PIXEL), extendedDepthLockedRect.pBits, extendedDepthTex->BufferLen());

    extendedDepthTex->UnlockRect(0);

    if(0 != err)
    {
        SetStatusMessage(L"Error copying extended depth texture pixels.");
        return hr;
    }

    return hr;
}

/// <summary>
/// Handle new depth data and perform Kinect Fusion processing
/// </summary>
void CKinectFusionBasics::ProcessDepth()
{
    if (m_bInitializeError)
    {
        return;
    }

    HRESULT hr = S_OK;
    NUI_IMAGE_FRAME imageFrame;

    ////////////////////////////////////////////////////////
    // Get an extended depth frame from Kinect

    hr = m_pNuiSensor->NuiImageStreamGetNextFrame(m_pDepthStreamHandle, 0, &imageFrame);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect NuiImageStreamGetNextFrame call failed.");
        return;
    }

    hr = CopyExtendedDepth(imageFrame);

    LARGE_INTEGER currentDepthFrameTime = imageFrame.liTimeStamp;

    // Release the Kinect camera frame
    m_pNuiSensor->NuiImageStreamReleaseFrame(m_pDepthStreamHandle, &imageFrame);

    if (FAILED(hr))
    {
        return;
    }

    // To enable playback of a .xed file through Kinect Studio and reset of the reconstruction
    // if the .xed loops, we test for when the frame timestamp has skipped a large number. 
    // Note: this will potentially continually reset live reconstructions on slow machines which
    // cannot process a live frame in less time than the reset threshold. Increase the number of
    // milliseconds in cResetOnTimeStampSkippedMilliseconds if this is a problem.
    if (m_bAutoResetReconstructionOnTimeout && m_cFrameCounter != 0 
        && abs(currentDepthFrameTime.QuadPart - m_cLastDepthFrameTimeStamp.QuadPart) > cResetOnTimeStampSkippedMilliseconds)
    {
        ResetReconstruction();

        if (FAILED(hr))
        {
            return;
        }
    }

    m_cLastDepthFrameTimeStamp = currentDepthFrameTime;

    // Return if the volume is not initialized
    if (nullptr == m_pVolume)
    {
        SetStatusMessage(L"Kinect Fusion reconstruction volume not initialized. Please try reducing volume size or restarting.");
        return;
    }

    ////////////////////////////////////////////////////////
    // Depth to DepthFloat

    // Convert the pixels describing extended depth as unsigned short type in millimeters to depth
    // as floating point type in meters.
    hr = m_pVolume->DepthToDepthFloatFrame(m_pDepthImagePixelBuffer, m_cDepthImagePixels * sizeof(NUI_DEPTH_IMAGE_PIXEL), m_pDepthFloatImage, m_fMinDepthThreshold, m_fMaxDepthThreshold, m_bMirrorDepthFrame);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion NuiFusionDepthToDepthFloatFrame call failed.");
        return;
    }

    ////////////////////////////////////////////////////////
    // ProcessFrame

    // Perform the camera tracking and update the Kinect Fusion Volume
    // This will create memory on the GPU, upload the image, run camera tracking and integrate the
    // data into the Reconstruction Volume if successful. Note that passing nullptr as the final 
    // parameter will use and update the internal camera pose.
    hr = m_pVolume->ProcessFrame(m_pDepthFloatImage, 15, m_cMaxIntegrationWeight, &m_worldToCameraTransform);

    // Test to see if camera tracking failed. 
    // If it did fail, no data integration or raycast for reference points and normals will have taken 
    //  place, and the internal camera pose will be unchanged.
    if (FAILED(hr))
    {
        if (hr == E_NUI_FUSION_TRACKING_ERROR)
        {
            m_cLostFrameCounter++;
            m_bTrackingFailed = true;
            SetStatusMessage(L"Kinect Fusion camera tracking failed! Align the camera to the last tracked position. ");
        }
        else
        {
            SetStatusMessage(L"Kinect Fusion ProcessFrame call failed!");
            return;
        }
    }
    else
    {
        m_depthFrameCount++;
    }

    //if (m_bAutoResetReconstructionWhenLost && m_bTrackingFailed && m_cLostFrameCounter >= cResetOnNumberOfLostFrames)
    //{
    //    // Automatically clear volume and reset tracking if tracking fails
    //    hr = ResetReconstruction();

    //    if (FAILED(hr))
    //    {
    //        return;
    //    }

    //    // Set bad tracking message
    //    SetStatusMessage(L"Kinect Fusion camera tracking failed, automatically reset volume.");
    //}

    //////////////////////////////////////////////////////////
    //// CalculatePointCloud

    //// Raycast all the time, even if we camera tracking failed, to enable us to visualize what is happening with the system
    //hr = m_pVolume->CalculatePointCloud(m_pPointCloud, &m_worldToCameraTransform);

    //if (FAILED(hr))
    //{
    //    SetStatusMessage(L"Kinect Fusion CalculatePointCloud call failed.");
    //    return;
    //}

    //////////////////////////////////////////////////////////
    //// ShadePointCloud and render

    //hr = NuiFusionShadePointCloud(m_pPointCloud, &m_worldToCameraTransform, nullptr, m_pShadedSurface, nullptr);

    //if (FAILED(hr))
    //{
    //    SetStatusMessage(L"Kinect Fusion NuiFusionShadePointCloud call failed.");
    //    return;
    //}

    //// Draw the shaded raycast volume image
    //INuiFrameTexture * pShadedImageTexture = m_pShadedSurface->pFrameTexture;
    //NUI_LOCKED_RECT ShadedLockedRect;

    //// Lock the frame data so the Kinect knows not to modify it while we're reading it
    //hr = pShadedImageTexture->LockRect(0, &ShadedLockedRect, nullptr, 0);
    //if (FAILED(hr))
    //{
    //    return;
    //}

    //// Make sure we've received valid data
    //if (ShadedLockedRect.Pitch != 0)
    //{
    //    BYTE * pBuffer = (BYTE *)ShadedLockedRect.pBits;

    //    // Draw the data with Direct2D
    //    m_pDrawDepth->Draw(pBuffer, m_cDepthWidth * m_cDepthHeight * cBytesPerPixel);
    //}

    //// We're done with the texture so unlock it
    //pShadedImageTexture->UnlockRect(0);

    //////////////////////////////////////////////////////////
    //// Periodically Display Fps

    //// Update frame counter
    //m_cFrameCounter++;

    //// Display fps count approximately every cTimeDisplayInterval seconds
    //double elapsed = m_timer.AbsoluteTime() - m_fStartTime;
    //if ((int)elapsed >= cTimeDisplayInterval)
    //{
    //    double fps = (double)m_cFrameCounter / elapsed;
    //
    //    // Update status display
    //    if (!m_bTrackingFailed)
    //    {
    //        WCHAR str[MAX_PATH];
    //        swprintf_s(str, ARRAYSIZE(str), L"Fps: %5.2f", fps);
    //        SetStatusMessage(str);
    //    }

    //    m_cFrameCounter = 0;
    //    m_fStartTime = m_timer.AbsoluteTime();
    //}
}


/// <summary>
/// Reset the reconstruction camera pose and clear the volume.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT CKinectFusionBasics::ResetReconstruction()
{
    if (nullptr == m_pVolume)
    {
        return E_FAIL;
    }

    HRESULT hr = S_OK;

    SetIdentityMatrix(m_worldToCameraTransform);

    // Translate the reconstruction volume location away from the world origin by an amount equal
    // to the minimum depth threshold. This ensures that some depth signal falls inside the volume.
    // If set false, the default world origin is set to the center of the front face of the 
    // volume, which has the effect of locating the volume directly in front of the initial camera
    // position with the +Z axis into the volume along the initial camera direction of view.
    if (m_bTranslateResetPoseByMinDepthThreshold)
    {
        Matrix4 worldToVolumeTransform = m_defaultWorldToVolumeTransform;

        // Translate the volume in the Z axis by the minDepthThreshold distance
        float minDist = (m_fMinDepthThreshold < m_fMaxDepthThreshold) ? m_fMinDepthThreshold : m_fMaxDepthThreshold;
        worldToVolumeTransform.M43 -= (minDist * m_reconstructionParams.voxelsPerMeter);

        hr = m_pVolume->ResetReconstruction(&m_worldToCameraTransform, &worldToVolumeTransform);
    }
    else
    {
        hr = m_pVolume->ResetReconstruction(&m_worldToCameraTransform, nullptr);
    }

    m_cLostFrameCounter = 0;
    m_cFrameCounter = 0;
    m_fStartTime = m_timer.AbsoluteTime();

    if (SUCCEEDED(hr))
    {
        m_bTrackingFailed = false;

        SetStatusMessage(L"Reconstruction has been reset.");
    }
    else
    {
        SetStatusMessage(L"Failed to reset reconstruction.");
    }

    return hr;
}

/// <summary>
/// Set the status bar message
/// </summary>
/// <param name="szMessage">message to display</param>
void CKinectFusionBasics::SetStatusMessage(WCHAR * szMessage)
{
    SendDlgItemMessageW(m_hWnd, IDC_STATUS, WM_SETTEXT, 0, (LPARAM)szMessage);
}
