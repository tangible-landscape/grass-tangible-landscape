//------------------------------------------------------------------------------
// <copyright file="Timer.cpp" company="Microsoft">
// 	 
//	 Copyright 2013 Microsoft Corporation 
// 	 
//	Licensed under the Apache License, Version 2.0 (the "License"); 
//	you may not use this file except in compliance with the License.
//	You may obtain a copy of the License at
// 	 
//		 http://www.apache.org/licenses/LICENSE-2.0 
// 	 
//	Unless required by applicable law or agreed to in writing, software 
//	distributed under the License is distributed on an "AS IS" BASIS,
//	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
//	See the License for the specific language governing permissions and 
//	limitations under the License. 
// 	 
// </copyright>
//------------------------------------------------------------------------------

#include "Timer.h"

namespace Timing
{

Timer::Timer()
{
    if (QueryPerformanceFrequency(&frequency) == 0)
    {
        // Frequency not supported - cannot get time!
        initialized = false;
        return;
    }

    initialized = true;
}

/// <summary>
///  Gets the absolute time.
/// </summary>
/// <returns>Returns the absolute time in s.</returns>
double Timer::AbsoluteTime()
{
    if (initialized == false)
    {
        return 0;
    }

    LARGE_INTEGER systemTime;
    if (QueryPerformanceCounter(&systemTime) == 0)
    {
        return 0;
    }
    double realTime = (double)systemTime.QuadPart / (double)frequency.QuadPart;
    return realTime;
}

};
